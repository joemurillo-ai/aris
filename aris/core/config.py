import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

def load_dotenv(path: Optional[Path] = None) -> None:
    """
    Minimal .env loader (KEY=VALUE lines). Ignores comments.
    Does not override existing env vars.
    """
    p = path or Path(".env")
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        os.environ.setdefault(k, v)

@dataclass(frozen=True)
class Settings:
    aris_home: Path = Path(os.getenv("ARIS_HOME", Path.cwd()))
    logs_dir: Path = Path(os.getenv("ARIS_LOGS_DIR", "logs"))
    secrets_backend: str = os.getenv("ARIS_SECRETS_BACKEND", "env")  # env|keyring|vault
    vault_addr: Optional[str] = os.getenv("VAULT_ADDR")
    vault_token: Optional[str] = os.getenv("VAULT_TOKEN")
