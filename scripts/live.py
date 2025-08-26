import argparse
import sys
from pathlib import Path

import zmq

from quanttime.execution.executor import LiveExecutor, RiskLimits
from quanttime.utils.config import AppConfig


def main():
    parser = argparse.ArgumentParser(description="Subscribe to ticks and place toy orders under risk limits")
    parser.add_argument("--threshold", type=float, default=0.0, help="Toy price-change threshold to trade")
    args = parser.parse_args()

    cfg = AppConfig()
    ctx = zmq.Context.instance()
    sock = ctx.socket(zmq.SUB)
    sock.connect(cfg.zmq_sub_endpoint)
    sock.setsockopt_string(zmq.SUBSCRIBE, "ticks")

    executor = LiveExecutor(RiskLimits(max_position=cfg.risk_max_position, max_daily_loss=cfg.risk_max_daily_loss))
    last_price = None
    try:
        while True:
            topic, payload = sock.recv_multipart()
            msg = json.loads(payload.decode("utf-8"))
            price = float(msg["price"])
            if last_price is not None:
                change = price - last_price
                if change > args.threshold:
                    executor.market_order("buy", 1, price)
                elif change < -args.threshold:
                    executor.market_order("sell", 1, price)
            last_price = price
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()


