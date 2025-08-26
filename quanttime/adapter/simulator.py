import time
import threading
import random
from typing import Optional, Iterator
from quanttime.adapter.publisher import ZmqPublisher
from quanttime.utils.logging import get_logger


def synthetic_ticks(start_price: float = 5000.0) -> Iterator[dict]:
    price = start_price
    while True:
        step = random.choice([-1, 0, 1]) * random.choice([0.25, 0.5, 0.75, 1.0])
        price = max(0.25, price + step)
        size = random.choice([1, 2, 3, 5, 8])
        side = "buy" if step >= 0 else "sell"
        yield {"ts": time.time(), "price": price, "size": size, "side": side}
        time.sleep(0.01)


def run_tick_simulator(endpoint: str) -> None:
    logger = get_logger("TickSimulator")
    pub = ZmqPublisher(endpoint)
    pub.start()
    logger.info("Starting synthetic tick stream on %s", endpoint)
    try:
        for msg in synthetic_ticks():
            pub.publish("ticks", msg)
    except KeyboardInterrupt:
        logger.info("Simulator stopped")
    finally:
        pub.stop()


