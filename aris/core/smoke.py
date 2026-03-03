# aris/core/smoke.py
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from aris.core.config import load_dotenv, Settings
from aris.core.runner import run_agent


@dataclass(frozen=True)
class SmokeReport:
    ok: bool
    lines: list[str]


def _file_mode(path: Path) -> int | None:
    try:
        return path.stat().st_mode & 0o777
    except FileNotFoundError:
        return None


def _new_log_written_since(logs_dir: Path, started_at: float) -> bool:
    try:
        newest = max(logs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, default=None)
        if newest is None:
            return False
        # 2-second safety window for filesystem timestamp quirks
        return newest.stat().st_mtime >= (started_at - 2.0)
    except Exception:
        return False


def smoke(env_path: Path | None = None, agent: str = "planner", prompt: str = "smoke") -> SmokeReport:
    lines: list[str] = []
    ok = True

    # 1) Load env + settings
    load_dotenv(env_path or Path(".env"))
    settings = Settings.from_env()

    # 2) Config checks
    logs_dir = Path(settings.logs_dir)
    lines.append(f"logs_dir: {logs_dir}")

    # .env checks (best-effort)
    env_file = env_path or Path(".env")
    if env_file.exists():
        mode = _file_mode(env_file)
        lines.append(f".env: OK ({env_file}) perm={oct(mode) if mode is not None else 'unknown'}")
        if mode is not None and mode != 0o600:
            lines.append("WARN: recommended chmod 600 .env")
    else:
        lines.append(f".env: MISSING ({env_file})")
        ok = False

    # Logs dir writable
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        testfile = logs_dir / ".smoke_write_test"
        testfile.write_text("ok")
        testfile.unlink(missing_ok=True)
        lines.append("logs: OK (writable)")
    except Exception as e:
        lines.append(f"logs: FAIL (not writable) {e}")
        ok = False

    # Secret presence
    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key.startswith("sk-"):
        lines.append("OPENAI_API_KEY: OK")
    else:
        lines.append("OPENAI_API_KEY: MISSING/INVALID")
        ok = False

    # If config is already broken, stop early
    if not ok:
        lines.append("smoke: FAIL (preflight)")
        return SmokeReport(ok=False, lines=lines)

    # 3) Minimal model call + 4) verify ledger/log write
    started_at = time.time()
    try:
        out = run_agent(prompt, agent, logs_dir)
        lines.append(f"model_call: OK (agent={agent})")
        if not out or not str(out).strip():
            lines.append("WARN: model output empty")
    except Exception as e:
        lines.append(f"model_call: FAIL {e}")
        lines.append("smoke: FAIL")
        return SmokeReport(ok=False, lines=lines)

    # Verify a new log appeared after we started
    if _new_log_written_since(logs_dir, started_at):
        lines.append("ledger/log: OK (new log entry detected)")
        lines.append("smoke: OK")
        return SmokeReport(ok=True, lines=lines)

    lines.append("ledger/log: FAIL (no new log file detected)")
    lines.append("smoke: FAIL")
    return SmokeReport(ok=False, lines=lines)
