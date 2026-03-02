from pathlib import Path
from typing import List

from aris.core.config import Settings, load_dotenv
from aris.core.secrets import get_secret

def secrets_check(names: List[str]) -> int:
    load_dotenv(Path(".env"))
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
