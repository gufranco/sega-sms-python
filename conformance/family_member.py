from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import segasms  # noqa: E402

FAMILY = (ROOT / "FAMILY.md").read_text()

KIND = "Board"

PACKAGE: ModuleType = segasms

TOOL_MODULES = {"doctor", "environment", "record"}

TESTED_DIRECTORIES = ("segasms", "conformance", "window")
