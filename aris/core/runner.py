from pathlib import Path
from typing import Optional

from .agents import get_agent
from .ledger import RunLedger
from aris.utils.logging import get_logger

log = get_logger("aris.runner")

def run_agent(prompt: str, agent_name: str, logs_dir: Path) -> str:
    ledger = RunLedger(logs_dir)
    rec = ledger.start(cmd="run", input_text=prompt, agent=agent_name)

    try:
        agent = get_agent(agent_name)
        log.info("agent_start", extra={"event":"agent_start", "run_id": rec.run_id, "ctx":{"agent": agent_name}})
        out = agent.handler(prompt)
        ledger.finish(rec, out, status="ok")
        log.info("agent_ok", extra={"event":"agent_ok", "run_id": rec.run_id, "ctx":{"agent": agent_name}})
        return out
    except Exception as e:
        ledger.fail(rec, str(e))
        log.error("agent_error", extra={"event":"agent_error", "run_id": rec.run_id, "ctx":{"agent": agent_name}}, exc_info=True)
        raise
