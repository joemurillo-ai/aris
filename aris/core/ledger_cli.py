import json
from pathlib import Path
from typing import Optional

def _latest_json(logs_dir: Path) -> Optional[Path]:
    if not logs_dir.exists():
        return None
    files = sorted(logs_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return files[0] if files else None

def ledger_latest(logs_dir: Path) -> int:
    p = _latest_json(logs_dir)
    if not p:
        print("No ledger files found.")
        return 1
    print(p.name.replace(".json", ""))
    return 0

def ledger_show(run_id: str, logs_dir: Path) -> int:
    p = logs_dir / f"{run_id}.json"
    if not p.exists():
        print(f"Not found: {p}")
        return 1
    obj = json.loads(p.read_text())
    print(json.dumps(obj, indent=2, ensure_ascii=False))
    return 0
