import os
from typing import Optional

def _env_get(name: str) -> Optional[str]:
    v = os.getenv(name)
    return v if v else None

def _keyring_get(name: str, service: str) -> Optional[str]:
    try:
        import keyring
    except Exception:
        return None
    try:
        v = keyring.get_password(service, name)
        return v if v else None
    except Exception:
        return None

def get_secret(name: str, settings=None) -> Optional[str]:
    backend = getattr(settings, "secrets_backend", "env") if settings else "env"
    service = getattr(settings, "secrets_service", "aris") if settings else "aris"

    if backend == "keyring":
        return _keyring_get(name, service) or _env_get(name)

    return _env_get(name) or _keyring_get(name, service)
