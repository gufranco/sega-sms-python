import json
from pathlib import Path
from typing import Any

HELD: dict[str, Any] = json.loads((Path(__file__).resolve().parent / "hardware.json").read_text())

FACTS: dict[str, Any] = HELD["facts"]

UNSTATED: dict[str, Any] = HELD["notStated"]
