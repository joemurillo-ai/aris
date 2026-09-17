import socket
import time
from pathlib import Path
from typing import Optional

from .agents import get_agent
from .ledger import RunLedger
from .llm import LLMResult
from .authorization import authorize_call
from aris.utils.logging import get_logger

log = get_logger("aris.runner")


def run_agent(
    prompt: str,
    agent_name: str,
    logs_dir: Path,
    mission_id: Optional[str] = None,
) -> str:
    if mission_id is not None:
        authorize_call(logs_dir, mission_id, agent_name)
    ledger = RunLedger(logs_dir)

    rec = ledger.start(
        cmd="run",
        input_text=prompt,
        agent=agent_name,
        mission_id=mission_id,
        meta={
            "node_id": socket.gethostname(),
        },
    )

    started = time.perf_counter()

    try:
        agent = get_agent(agent_name)

        log.info(
            "agent_start",
            extra={
                "event": "agent_start",
                "run_id": rec.run_id,
                "ctx": {
                    "agent": agent_name,
                    "mission_id": mission_id,
                },
            },
        )

        result = agent.handler(prompt)

        if isinstance(result, LLMResult):
            out = result.text
            rec.meta.update(result.meta)
        else:
            out = result

        rec.meta["latency_ms"] = round(
            (time.perf_counter() - started) * 1000
        )

        ledger.finish(rec, out, status="ok")

        log.info(
            "agent_ok",
            extra={
                "event": "agent_ok",
                "run_id": rec.run_id,
                "ctx": {
                    "agent": agent_name,
                    "mission_id": mission_id,
                },
            },
        )

        return out

    except Exception as e:
        rec.meta["latency_ms"] = round(
            (time.perf_counter() - started) * 1000
        )

        ledger.fail(rec, str(e))

        log.error(
            "agent_error",
            extra={
                "event": "agent_error",
                "run_id": rec.run_id,
                "ctx": {
                    "agent": agent_name,
                    "mission_id": mission_id,
                },
            },
            exc_info=True,
        )

        raise
