import os
from typing import Optional

from .config import Settings
from aris.utils.logging import get_logger

log = get_logger("aris.secrets")

def get_secret(name: str, settings: Settings) -> Optional[str]:
    """
    Resolution order:
      1) Environment variable (ARIS_ pref allowed)
      2) keyring (if installed) when ARIS_SECRETS_BACKEND=keyring
      3) Vault stub (when backend=vault) - requires requests (optional)
    """
    # 1) env
    if name in os.environ:
        return os.environ.get(name)
    pref = f"ARIS_{name}"
    if pref in os.environ:
        return os.environ.get(pref)

    backend = (settings.secrets_backend or "env").lower()

    # 2) keyring (optional)
    if backend == "keyring":
        try:
            import keyring  # type: ignore
            return keyring.get_password("aris", name)
        except Exception as e:
            log.warning("keyring_unavailable", extra={"event":"keyring_unavailable", "ctx":{"err": str(e)}})
            return None

    # 3) vault (optional stub)
    if backend == "vault":
        # Intentionally minimal: you can wire real Vault later.
        # For now rely on VAULT_ADDR/VAULT_TOKEN being set and implement when ready.
        log.warning("vault_not_implemented", extra={"event":"vault_not_implemented"})
        return None

    return None
