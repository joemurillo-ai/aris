import json
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from aris.core.mission import Mission


class MissionRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, mission: Mission) -> Path:
        path = self.root / f"{mission.mission_id}.json"
        path.write_text(
            json.dumps(
                asdict(mission),
                ensure_ascii=False,
                indent=2,
            )
        )
        return path

    def get(self, mission_id: str) -> Optional[Mission]:
        path = self.root / f"{mission_id}.json"

        if not path.exists():
            return None

        data = json.loads(path.read_text())
        return Mission(**data)

    def list(self) -> List[Mission]:
        missions = []

        for path in sorted(self.root.glob("*.json")):
            data = json.loads(path.read_text())
            missions.append(Mission(**data))

        return missions
