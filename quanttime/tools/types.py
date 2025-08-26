from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class CheckResult:
    name: str
    ok: bool
    details: Dict[str, Any]
    error: Optional[str] = None


