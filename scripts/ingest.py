import sys
from quanttime.adapter.simulator import run_tick_simulator
from quanttime.utils.config import AppConfig


def main():
    parser = argparse.ArgumentParser(description="Ingest from Sierra or simulator and publish via ZeroMQ")
    parser.add_argument("--simulate", action="store_true", help="Use synthetic simulator instead of Sierra DTC")
    parser.add_argument("--publish", action="store_true", help="Publish to ZeroMQ PUB endpoint")
    args = parser.parse_args()

    cfg = AppConfig()
    if args.simulate and args.publish:
        run_tick_simulator(cfg.zmq_pub_endpoint)
    else:
        print("DTC ingestion not yet implemented in this scaffold. Use --simulate --publish for now.")


if __name__ == "__main__":
    main()


