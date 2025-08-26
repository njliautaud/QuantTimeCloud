import json
import time
import threading
from typing import Dict, Any, Optional
import zmq
from quanttime.utils.logging import get_logger


class ZmqPublisher:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.ctx = zmq.Context.instance()
        self.sock = self.ctx.socket(zmq.PUB)
        self.logger = get_logger(self.__class__.__name__)

    def start(self):
        self.sock.bind(self.endpoint)
        # Allow subscribers to connect
        time.sleep(0.2)
        self.logger.info(f"ZeroMQ PUB bound at {self.endpoint}")

    def stop(self):
        try:
            self.sock.close(0)
        finally:
            self.ctx.term()

    def publish(self, topic: str, payload: Dict):
        self.sock.send_multipart([topic.encode("utf-8"), json.dumps(payload).encode("utf-8")])


