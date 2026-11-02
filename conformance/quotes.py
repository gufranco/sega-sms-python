import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from conformance import manual

RECORDS = Path(__file__).resolve().parent

EXTERNAL = RECORDS.parent / "external"

KEPT = ("hardware.json",)

Quote = tuple[str, str]

Cited = tuple[str, str, str]


def _quoted(key: str, value: Any, where: str) -> list[Quote]:
    if key.endswith("quote") and isinstance(value, str):
        return [(where, value)]
    if key.endswith("quotes") and isinstance(value, list):
        return [(f"{where}[{index}]", one) for index, one in enumerate(value)]
    return []


def passages(node: Any, where: str) -> list[Quote]:
    if isinstance(node, list):
        return [
            found for index, one in enumerate(node) for found in passages(one, f"{where}[{index}]")
        ]
    if not isinstance(node, dict) or "file" in node:
        return []
    found: list[Quote] = []
    for key, value in node.items():
        held = _quoted(key, value, where)
        found += held if held else passages(value, f"{where}.{key}")
    return found


def citations(node: Any, where: str) -> list[Cited]:
    if isinstance(node, list):
        return [
            found for index, one in enumerate(node) for found in citations(one, f"{where}[{index}]")
        ]
    if not isinstance(node, dict):
        return []
    if "file" in node and "quote" in node:
        return [(where, node["quote"], node["file"])]
    return [found for key, value in node.items() for found in citations(value, f"{where}.{key}")]


def _records(where: Path = RECORDS) -> list[tuple[str, Any]]:
    return [(name, json.loads((where / name).read_text())) for name in KEPT]


def collected(where: Path = RECORDS) -> list[Quote]:
    return [found for name, record in _records(where) for found in passages(record, name)]


def cited(where: Path = RECORDS) -> list[Cited]:
    return [found for name, record in _records(where) for found in citations(record, name)]


def absent(held: Sequence[Quote], text: str) -> list[Quote]:
    flat = manual.flatten(text)
    return [(where, quote) for where, quote in held if manual.flatten(quote) not in flat]


def check_sources(held: Sequence[Cited], root: Path) -> tuple[int, list[Quote]]:
    checked = 0
    missing: list[Quote] = []
    for where, quote, file in held:
        path = root / file
        if not path.is_file():
            continue
        checked += 1
        missing += absent([(where, quote)], path.read_text(encoding="utf-8", errors="replace"))
    return checked, missing


def check_manual(held: Sequence[Quote], body: str) -> list[Quote]:
    if not body:
        print(
            f"{len(held)} quotes checked against 0 documents: the manual is not on this "
            "machine, so none was checked. It is not redistributable and is named in the "
            "References section of README.md"
        )
        return []
    missing = absent(held, body)
    print(
        f"{len(held)} quotes against 1 document, {len(held) - len(missing)} located, {len(missing)} not"
    )
    return missing


def main(text: str | None = None, sources: Path = EXTERNAL, records: Path = RECORDS) -> int:
    missing = check_manual(collected(records), manual.text() if text is None else text)
    held = cited(records)
    checked, unfound = check_sources(held, sources)
    print(
        f"{len(held)} quotes from source code, {checked} checked against the pinned checkouts"
        f" in external/, {checked - len(unfound)} located, {len(unfound)} not,"
        f" {len(held) - checked} not checked because their checkout is not here"
    )
    for where, quote in [*missing, *unfound]:
        print(f"  {where}: {quote}")
    return 1 if missing or unfound else 0


if __name__ == "__main__":
    sys.exit(main())
