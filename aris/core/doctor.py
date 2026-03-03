from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from aris.core.config import load_dotenv, Settings


@dataclass(frozen=True)
class DoctorReport:
    ok: bool
    lines: list[str]


def _run(cmd: list[str]) -> Tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True)
        out = (p.stdout or "").strip()
        err = (p.stderr or "").strip()
        merged = "\n".join([x for x in [out, err] if x])
        return p.returncode, merged
    except Exception as e:
        return 1, str(e)


def _is_venv_active() -> bool:
    return (
        hasattr(sys, "base_prefix") and sys.prefix != sys.base_prefix
    ) or bool(os.getenv("VIRTUAL_ENV"))


def _file_mode(path: Path) -> Optional[int]:
    try:
        return path.stat().st_mode & 0o777
    except FileNotFoundError:
        return None


def doctor(env_path: Optional[Path] = None) -> DoctorReport:
    load_dotenv(env_path)
    settings = Settings.from_env()

    lines: list[str] = []
    ok = True

    lines.append(f"python: {sys.version.split()[0]}")
    lines.append(f"venv: {'OK' if _is_venv_active() else 'NO (activate .venv)'}")
    if not _is_venv_active():
        ok = False

    rc, out = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if rc == 0:
        lines.append(f"git branch: {out}")
        rc2, out2 = _run(["git", "status", "-sb"])
        if rc2 == 0:
            dirty = (" M " in out2) or ("??" in out2)
            lines.append(f"git status: {'DIRTY' if dirty else 'CLEAN'}")
    else:
        lines.append("git: not available (ok)")

    cwd = Path.cwd()
    env_file = env_path if env_path is not None else (cwd / ".env")
    if env_file.exists():
        mode = _file_mode(env_file)
        lines.append(f".env: OK ({env_file}) perm={oct(mode) if mode is not None else 'unknown'}")
        if mode is not None and mode != 0o600:
            lines.append("WARN: recommended chmod 600 .env")
    else:
        lines.append(f".env: MISSING ({env_file})")
        ok = False

    logs_dir = Path(settings.logs_dir)
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
        testfile = logs_dir / ".write_test"
        testfile.write_text("ok")
        testfile.unlink(missing_ok=True)
        lines.append(f"logs dir: OK ({logs_dir})")
    except Exception as e:
        lines.append(f"logs dir: FAIL ({logs_dir}) {e}")
        ok = False

    api_key = os.getenv("OPENAI_API_KEY", "")
    if api_key and api_key.startswith("sk-"):
        lines.append("OPENAI_API_KEY: OK")
    else:
        lines.append("OPENAI_API_KEY: MISSING/INVALID (set in .env)")
        ok = False

    lines.append(f"overall: {'OK' if ok else 'FAIL'}")
    return DoctorReport(ok=ok, lines=lines)
