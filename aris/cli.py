import argparse
from datetime import datetime
from pathlib import Path

from aris.core.config import Settings, load_dotenv
from aris.core.doctor import doctor as run_doctor
from aris.core.smoke import smoke as run_smoke
from aris.core.agents import list_agents
from aris.core.runner import run_agent
from aris.core.orchestrator import run_review_chain
from aris.core.ledger_cli import ledger_latest, ledger_show
from aris.core.secrets_cli import secrets_check, secrets_set
from aris.core.missions_cli import missions_summary, missions_list, missions_show, missions_approve, missions_deny, missions_quarantine, missions_release, missions_retry
from aris.core.mission_policy import MISSION_STATUSES, MISSION_HEALTHS
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

    smoke_p = sub.add_parser("smoke", help="Operator smoke test (config + model call + ledger write)")
    smoke_p.add_argument("--env", default=".env", help="Path to .env (default: .env)")
    smoke_p.add_argument("--agent", default="planner", help="Agent to call (default: planner)")
    smoke_p.add_argument("--prompt", default="smoke", help="Prompt for the smoke call")

    hello = sub.add_parser("hello", help="greet")
    hello.add_argument("name", nargs="?", default="Operator")

    sub.add_parser("agents", help="list available agents")

    r = sub.add_parser("run", help="run an agent")
    r.add_argument("agent", help="agent name (e.g., planner, echo)")
    r.add_argument("prompt", nargs="+", help="prompt text")

    review = sub.add_parser("review", help="run planner -> analyst -> critic chain")
    review.add_argument("prompt", nargs="+", help="mission text")

    pl = sub.add_parser("planner", help="shortcut: run planner agent")
    pl.add_argument("prompt", nargs="+", help="prompt text")

    led = sub.add_parser("ledger", help="inspect run ledger")
    led_sub = led.add_subparsers(dest="ledger_cmd")

    led_sub.add_parser("latest", help="print newest run_id")

    show = led_sub.add_parser("show", help="pretty-print a ledger file by run_id")
    show.add_argument("run_id", help="run id (filename without .json)")

    missions = sub.add_parser("missions", help="ARIS Mission Control")
    missions_sub = missions.add_subparsers(dest="missions_cmd")

    mission_list = missions_sub.add_parser("list", help="list missions")
    mission_list.add_argument("--status", type=str.lower, choices=MISSION_STATUSES)
    mission_list.add_argument("--health", type=str.upper, choices=MISSION_HEALTHS)
    missions_sub.add_parser("summary", help="summarize mission status and health")

    mission_show = missions_sub.add_parser("show", help="show mission details")
    mission_show.add_argument("mission_id", help="mission id")

    mission_approve = missions_sub.add_parser(
        "approve",
        help="approve a mission awaiting approval",
    )
    mission_approve.add_argument("mission_id", help="mission id")
    mission_approve.add_argument(
        "--actor",
        required=True,
        help="operator approving the mission",
    )

    mission_deny = missions_sub.add_parser(
        "deny",
        help="deny a mission awaiting approval",
    )
    mission_deny.add_argument("mission_id", help="mission id")
    mission_deny.add_argument(
        "--actor",
        required=True,
        help="operator denying the mission",
    )
    mission_deny.add_argument(
        "--reason",
        help="optional denial reason",
    )

    mission_quarantine = missions_sub.add_parser(
        "quarantine",
        help="quarantine a mission before execution",
    )
    mission_quarantine.add_argument("mission_id", help="mission id")
    mission_quarantine.add_argument(
        "--actor",
        required=True,
        help="operator quarantining the mission",
    )
    mission_quarantine.add_argument(
        "--reason",
        help="optional quarantine reason",
    )

    mission_release = missions_sub.add_parser(
        "release",
        help="release a quarantined mission",
    )
    mission_release.add_argument("mission_id", help="mission id")
    mission_release.add_argument(
        "--actor",
        required=True,
        help="operator releasing the mission",
    )
    mission_release.add_argument(
        "--reason",
        help="optional release reason",
    )

    mission_retry = missions_sub.add_parser(
        "retry",
        help="create a new retry attempt from an eligible mission",
    )
    mission_retry.add_argument("mission_id", help="mission id")
    mission_retry.add_argument(
        "--actor",
        required=True,
        help="operator creating the retry",
    )
    mission_retry.add_argument(
        "--reason",
        help="optional retry reason",
    )

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
    if args.cmd == "smoke":
        report = run_smoke(Path(args.env), agent=args.agent, prompt=args.prompt)
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

    if args.cmd == "review":
        mission = " ".join(args.prompt)
        out = run_review_chain(mission, logs_dir=logs_dir)
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

    if args.cmd == "missions":
        if args.missions_cmd == "list":
            return missions_list(logs_dir, status=args.status, health=args.health)
        if args.missions_cmd == "summary":
            return missions_summary(logs_dir)
        if args.missions_cmd == "show":
            return missions_show(args.mission_id, logs_dir)
        if args.missions_cmd == "approve":
            return missions_approve(
                args.mission_id,
                args.actor,
                logs_dir,
            )
        if args.missions_cmd == "deny":
            return missions_deny(
                args.mission_id,
                args.actor,
                args.reason,
                logs_dir,
            )
        if args.missions_cmd == "quarantine":
            return missions_quarantine(
                args.mission_id,
                args.actor,
                args.reason,
                logs_dir,
            )
        if args.missions_cmd == "release":
            return missions_release(
                args.mission_id,
                args.actor,
                args.reason,
                logs_dir,
            )
        if args.missions_cmd == "retry":
            return missions_retry(
                args.mission_id,
                args.actor,
                args.reason,
                logs_dir,
            )
        missions.print_help()
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
