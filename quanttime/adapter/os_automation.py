import os
import sys
import subprocess
import time
import threading
from typing import Optional, List, Dict, Any
from pathlib import Path
import logging
import json
import signal
from datetime import datetime, timedelta

try:
    from pywinauto.application import Application
    from pywinauto.timings import TimeoutError as PyWinTimeoutError
except Exception:  # optional dependency, may be absent
    Application = None  # type: ignore
    PyWinTimeoutError = Exception  # type: ignore

from quanttime.utils.config import AppConfig
from quanttime.utils.logging import get_logger


@dataclass
class OSAutomationResult:
    ok: bool
    message: str = ""


class SierraOSAutomation:
    """Thin wrapper for OS-level automation to control Sierra UI gaps.

    For now, we only launch Sierra with a specified Chartbook and rely on ACSIL for most control.
    Hooks for pywinauto/uiautomation can be added later.
    """

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.logger = get_logger(self.__class__.__name__)

    def launch_sierra(self) -> OSAutomationResult:
        try:
            args = [self.cfg.sierra_chart_exe, f"/CB:{self.cfg.sierra_chartbook_path}"]
            subprocess.Popen(args, shell=False)
            self.logger.info("Launched Sierra Chart: %s", args)
            time.sleep(2.0)
            return OSAutomationResult(True, "Launched")
        except Exception as e:
            self.logger.exception("Failed to launch Sierra")
            return OSAutomationResult(False, str(e))

    def ensure_replay_panel(self) -> OSAutomationResult:
        # Try to ensure Replay panel is open using pywinauto, if available
        if Application is None:
            return OSAutomationResult(True, "pywinauto not installed; skipped")
        try:
            app = Application(backend="uia").connect(path=self.cfg.sierra_chart_exe)
            win = app.top_window()
            # Try menu navigation: Chart -> Replay Chart -> Replay Chart (Control Panel)
            try:
                win.menu_select("&Chart->&Replay Chart->Replay Chart (Control Panel)")
            except Exception:
                # Some layouts use different menu text; try a fallback hotkey Ctrl+R
                win.type_keys("^r")
            time.sleep(0.5)
            return OSAutomationResult(True, "Replay panel ensured")
        except Exception as e:
            self.logger.exception("Failed to ensure replay panel")
            return OSAutomationResult(False, str(e))

    def ensure_study_loaded(self, study_name: str) -> OSAutomationResult:
        """Ensure the ACSIL study is added to the active chart. Attempts via menu automation.

        Steps (typical):
        - Chart Settings -> Studies (F6)
        - Add Custom Study -> find `study_name`
        - Add -> OK
        """
        if Application is None:
            return OSAutomationResult(True, "pywinauto not installed; skipped")
        try:
            app = Application(backend="uia").connect(path=self.cfg.sierra_chart_exe)
            win = app.top_window()
            # Try to open Studies dialog (F6 default in Sierra)
            try:
                win.type_keys("{F6}")
                time.sleep(0.5)
            except Exception:
                pass
            dlg = app.window(title_re=".*Studies.*")
            if not dlg.exists(timeout=3):
                # Try menu as fallback: Analysis->Studies
                try:
                    win.menu_select("&Analysis->&Studies")
                    time.sleep(0.5)
                except Exception:
                    pass
            # In Studies window, attempt to select the Custom Study list and add the target study
            try:
                dlg.wait("visible", timeout=3)
                # Heuristic controls; labels vary by theme/language
                dlg.child_window(title_re=".*Add Custom Study.*", control_type="Button").click_input()
                time.sleep(0.3)
                sel = app.window(title_re=".*Add Custom Study.*")
                sel.wait("visible", timeout=3)
                # Enter study name in a search box if present
                try:
                    edit = sel.child_window(control_type="Edit")
                    edit.type_keys(study_name)
                    time.sleep(0.2)
                except Exception:
                    pass
                # Select from list and click Add
                try:
                    lst = sel.child_window(control_type="List")
                    lst.select(study_name)
                except Exception:
                    pass
                for btn_name in ["&Add", "Add", "&OK", "OK"]:
                    try:
                        sel.child_window(title=btn_name, control_type="Button").click_input()
                        time.sleep(0.2)
                    except Exception:
                        continue
                # Close Studies dialog via OK
                for btn_name in ["&OK", "OK", "Close"]:
                    try:
                        dlg.child_window(title=btn_name, control_type="Button").click_input()
                        break
                    except Exception:
                        continue
            except Exception:
                # If the UI path is brittle, return a soft failure; ACSIL might already be loaded.
                return OSAutomationResult(False, "Could not verify study add; may already be present")
            return OSAutomationResult(True, "Study ensured")
        except Exception as e:
            self.logger.exception("Failed to ensure study loaded")
            return OSAutomationResult(False, str(e))


