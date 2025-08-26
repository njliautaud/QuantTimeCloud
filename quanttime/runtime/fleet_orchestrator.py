import concurrent.futures
import datetime as dt
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sierraflow.runtime.acsil_orchestrator import ACSILOrchestrator, BacktestRequest
from sierraflow.utils.config import AppConfig
from sierraflow.utils.logging import get_logger


@dataclass
class FleetEndpoint:
    host: str
    port: int


def parse_endpoints(cfg: AppConfig) -> List[FleetEndpoint]:
    eps: List[FleetEndpoint] = []
    if cfg.acsil_endpoints_csv.strip():
        for tok in cfg.acsil_endpoints_csv.split(","):
            tok = tok.strip()
            if not tok:
                continue
            if ":" in tok:
                host, port_s = tok.split(":", 1)
                try:
                    eps.append(FleetEndpoint(host=host, port=int(port_s)))
                except Exception:
                    continue
    if not eps:
        eps.append(FleetEndpoint(host=cfg.acsil_host, port=cfg.acsil_port))
    return eps


class FleetOrchestrator:
    """Run backtests in parallel across multiple ACSIL endpoints (Sierra instances)."""

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.endpoints = parse_endpoints(cfg)
        self.logger = get_logger(self.__class__.__name__)

    def run_many(self, jobs: List[Dict]) -> List[Tuple[Dict, Optional[Dict], Optional[Exception]]]:
        tasks: List[Tuple[Dict, FleetEndpoint]] = []
        for i, job in enumerate(jobs):
            ep = self.endpoints[i % len(self.endpoints)]
            tasks.append((job, ep))

        def _run(job: Dict, ep: FleetEndpoint) -> Tuple[Dict, Optional[Dict], Optional[Exception]]:
            try:
                orch = ACSILOrchestrator(self.cfg, host=ep.host, port=ep.port)
                orch.connect()
                req = BacktestRequest(
                    run_id=int(job["run_id"]),
                    symbol=str(job["symbol"]),
                    start=_parse(job["start"]),
                    end=_parse(job["end"]),
                    study_params=job.get("study_params", {}),
                    replay_speed=int(job.get("replay_speed", self.cfg.sc_replay_speed)),
                    accurate_mode=bool(job.get("accurate_mode", self.cfg.sc_use_accurate_mode)),
                    all_charts=bool(job.get("all_charts", self.cfg.sc_replay_all_charts)),
                )
                res = orch.run_backtest(req)
                orch.close()
                return (job, res, None)
            except Exception as e:
                return (job, None, e)

        results: List[Tuple[Dict, Optional[Dict], Optional[Exception]]] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(self.endpoints)) as pool:
            futs = [pool.submit(_run, job, ep) for job, ep in tasks]
            for fut in concurrent.futures.as_completed(futs):
                results.append(fut.result())
        return results


def _parse(x: str) -> dt.datetime:
    return dt.datetime.fromisoformat(x)


