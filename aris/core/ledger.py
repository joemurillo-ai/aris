import json
import os
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

@dataclass
class RunRecord:
    run_id: str
    ts_start: str
    ts_end: Optional[str]
    cmd: str
    agent: Optional[str]
    input: str
    output: Optional[str]
    status: str  # started|ok|error
    meta: Dict[str, Any]

class RunLedger:
    def __init__(self, logs_dir: Path) -> None:
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def start(self, cmd: str, input_text: str, agent: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> RunRecord:
        run_id = os.getenv("ARIS_RUN_ID") or uuid.uuid4().hex[:12]
        rec = RunRecord(
            run_id=run_id,
            ts_start=_utc_iso(),
            ts_end=None,
            cmd=cmd,
            agent=agent,
            input=input_text,
            output=None,
            status="started",
            meta=meta or {},
        )
        self._write(rec)
        return rec

    def finish(self, rec: RunRecord, output_text: str, status: str = "ok") -> RunRecord:
        rec.output = output_text
        rec.status = status
        rec.ts_end = _utc_iso()
        self._write(rec)
        return rec

    def fail(self, rec: RunRecord, err: str) -> RunRecord:
        rec.output = err
        rec.status = "error"
        rec.ts_end = _utc_iso()
        self._write(rec)
        return rec

    def _write(self, rec: RunRecord) -> None:
        p = self.logs_dir / f"{rec.run_id}.json"
        p.write_text(json.dumps(asdict(rec), ensure_ascii=False, indent=2))
