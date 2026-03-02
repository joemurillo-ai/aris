import getpass
from typing import List

from aris.core.config import Settings, load_dotenv
from aris.core.secrets import get_secret

def secrets_check(names: List[str]) -> int:
    load_dotenv()
    settings = Settings()
    missing = 0
    for n in names:
        v = get_secret(n, settings)
        if v:
            print(f"{n}: OK")
        else:
            print(f"{n}: MISSING")
            missing += 1
    return 0 if missing == 0 else 2

def secrets_set(name: str) -> int:
    load_dotenv()
    settings = Settings()
    backend = getattr(settings, "secrets_backend", "env")
    service = getattr(settings, "secrets_service", "aris")

    if backend != "keyring":
        print("Refusing: set ARIS_SECRETS_BACKEND=keyring in .env to use secrets set.")
        return 2

    try:
        import keyring
    except Exception:
        print("keyring not installed. Run: pip install -e '.[secrets]'")
        return 2

    val = getpass.getpass(f"Enter value for {name} (hidden): ")
    if not val:
        print("Empty value; aborted.")
        return 2

    keyring.set_password(service, name, val)
    print(f"{name}: STORED (keyring:{service})")
    return 0
