from .types import CheckResult
import zmq
from quanttime.utils.config import AppConfig
import time


def run(timeout_ms: int = 500) -> CheckResult:
    try:
        cfg = AppConfig()
        ctx = zmq.Context.instance()
        pub = ctx.socket(zmq.PUB)
        pub.bind("inproc://testpub")
        sub = ctx.socket(zmq.SUB)
        sub.connect("inproc://testpub")
        sub.setsockopt_string(zmq.SUBSCRIBE, "ticks")
        # Allow subscription to propagate
        time.sleep(0.05)
        topic = "ticks"
        payload = b"{\"ts\":0,\"price\":1,\"size\":1,\"side\":\"buy\"}"
        pub.send_multipart([topic.encode("utf-8"), payload])
        poller = zmq.Poller()
        poller.register(sub, zmq.POLLIN)
        events = dict(poller.poll(timeout=timeout_ms))
        ok = sub in events and events[sub] == zmq.POLLIN
        details = {"endpoint": cfg.zmq_pub_endpoint, "inproc_ok": ok}
        pub.close(0)
        sub.close(0)
        return CheckResult(name="zmq", ok=ok, details=details)
    except Exception as e:
        return CheckResult(name="zmq", ok=False, details={}, error=str(e))


