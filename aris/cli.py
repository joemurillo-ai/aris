import argparse
from datetime import datetime

def main():
    p = argparse.ArgumentParser(prog="aris", description="ARIS CLI (Node 2)")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("ping", help="health check")

    hello = sub.add_parser("hello", help="greet")
    hello.add_argument("name", nargs="?", default="Operator")

    args = p.parse_args()

    if args.cmd == "ping":
        print("ARIS: ok")
        return

    if args.cmd == "hello":
        print(f"[{datetime.now().isoformat(timespec='seconds')}] Hello, {args.name}. ARIS is online.")
        return

    p.print_help()

if __name__ == "__main__":
    main()
