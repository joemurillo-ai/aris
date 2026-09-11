import socket
import time
from pathlib import Path

from .agents import get_agent
from .ledger import RunLedger
from .llm import LLMResult
from aris.utils.logging import get_logger

log = get_logger("aris.runner")


def run_agent(prompt: str, agent_name: str, logs_dir: Path) -> str:
    ledger = RunLedger(logs_dir)
    rec = ledger.start(
        cmd="run",
        input_text=prompt,
        agent=agent_name,
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
                "ctx": {"agent": agent_name},
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
                "ctx": {"agent": agent_name},
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
                "ctx": {"agent": agent_name},
            },
            exc_info=True,
        )
        raise
