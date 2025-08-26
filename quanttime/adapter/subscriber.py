import json
from typing import Iterator, Tuple

import zmq


def subscribe_ticks(endpoint: str, topic: str = "ticks") -> Iterator[Tuple[str, dict]]:
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.SUB)
    sock.connect(endpoint)
    sock.setsockopt_string(zmq.SUBSCRIBE, topic)
    while True:
        t, payload = sock.recv_multipart()
        yield t.decode("utf-8"), json.loads(payload.decode("utf-8"))


