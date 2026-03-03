import argparse
from datetime import datetime
from pathlib import Path

from aris.core.config import Settings, load_dotenv
from aris.core.doctor import doctor as run_doctor
from aris.core.agents import list_agents
from aris.core.runner import run_agent
from aris.core.ledger_cli import ledger_latest, ledger_show
from aris.core.secrets_cli import secrets_check, secrets_set
from aris.utils.logging import get_logger

log = get_logger("aris.cli")

def main() -> int:
    load_dotenv(Path('.env'))
    settings = Settings.from_env()
    logs_dir = Path(settings.logs_dir)

    p = argparse.ArgumentParser(prog="aris", description="ARIS CLI (Node 2)")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("ping", help="health check")
    doctor_p = sub.add_parser("doctor", help="System integrity check")
    doctor_p.add_argument("--env", default=".env", help="Path to .env (default: .env)")

    hello = sub.add_parser("hello", help="greet")
    hello.add_argument("name", nargs="?", default="Operator")

    sub.add_parser("agents", help="list available agents")

    r = sub.add_parser("run", help="run an agent")
    r.add_argument("agent", help="agent name (e.g., planner, echo)")
    r.add_argument("prompt", nargs="+", help="prompt text")

    pl = sub.add_parser("planner", help="shortcut: run planner agent")
    pl.add_argument("prompt", nargs="+", help="prompt text")

    led = sub.add_parser("ledger", help="inspect run ledger")
    led_sub = led.add_subparsers(dest="ledger_cmd")

    led_sub.add_parser("latest", help="print newest run_id")

    show = led_sub.add_parser("show", help="pretty-print a ledger file by run_id")
    show.add_argument("run_id", help="run id (filename without .json)")

    sec = sub.add_parser("secrets", help="secret utilities")
    sec_sub = sec.add_subparsers(dest="secrets_cmd")

    chk = sec_sub.add_parser("check", help="check if secrets are available")
    chk.add_argument("names", nargs="+", help="secret env var names")

    st = sec_sub.add_parser("set", help="store a secret (keyring backend)")
    st.add_argument("name", help="secret name")

    args = p.parse_args()

    if args.cmd == "ping":
        print("ARIS: ok")
        return 0
    if args.cmd == "doctor":
        report = run_doctor(Path(args.env))
        for line in report.lines:
            print(line)
        return 0 if report.ok else 1

    if args.cmd == "hello":
        print(f"[{datetime.now().isoformat(timespec='seconds')}] Hello, {args.name}. ARIS is online.")
        return 0

    if args.cmd == "agents":
        for ag in list_agents():
            print(f"- {ag.name}: {ag.description}")
        return 0

    if args.cmd == "run":
        prompt = " ".join(args.prompt)
        out = run_agent(prompt, args.agent, logs_dir=logs_dir)
        print(out)
        return 0

    if args.cmd == "planner":
        prompt = " ".join(args.prompt)
        out = run_agent(prompt, "planner", logs_dir=logs_dir)
        print(out)
        return 0

    if args.cmd == "ledger":
        if args.ledger_cmd == "latest":
            return ledger_latest(logs_dir)
        if args.ledger_cmd == "show":
            return ledger_show(args.run_id, logs_dir)
        led.print_help()
        return 1

    if args.cmd == "secrets":
        if args.secrets_cmd == "check":
            return secrets_check(args.names)
        if args.secrets_cmd == "set":
            return secrets_set(args.name)
        p.print_help()
        return 1

    p.print_help()
    return 1
