import os
from dataclasses import dataclass
from pathlib import Path

def load_dotenv(path: Path | None = None) -> None:
    try:
        from dotenv import load_dotenv as _load
    except Exception:
        return

    if path is not None:
        _load(dotenv_path=path, override=False)
        return

    repo_env = Path.cwd() / ".env"
    if repo_env.exists():
        _load(dotenv_path=repo_env, override=False)
        return

    _load(override=False)

@dataclass(frozen=True)
class Settings:
    logs_dir: str
    secrets_backend: str
    secrets_service: str

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            logs_dir=os.getenv("ARIS_LOGS_DIR", "logs"),
            secrets_backend=os.getenv("ARIS_SECRETS_BACKEND", "env"),
            secrets_service=os.getenv("ARIS_SECRETS_SERVICE", "aris"),
        )
