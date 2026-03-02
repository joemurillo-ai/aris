import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": _utc_iso(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # attach extras if present
        for k in ("run_id", "event", "ctx"):
            if hasattr(record, k):
                payload[k] = getattr(record, k)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

def get_logger(name: str = "aris", level: Optional[str] = None) -> logging.Logger:
    lvl = (level or os.getenv("ARIS_LOG_LEVEL") or "INFO").upper()
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(lvl)
    h = logging.StreamHandler()
    h.setFormatter(JsonFormatter())
    logger.addHandler(h)
    logger.propagate = False
    return logger
