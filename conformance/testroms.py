import hashlib
import json
import os
import sys
import zipfile
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import smsmapper

import segasms

RECORD = Path(__file__).resolve().parent / "testroms.json"

PLACES = "TEST_CARTRIDGES"

KEPT = (
    Path(__file__).resolve().parent.parent
    / "external"
    / "Master EverDrive"
    / "5 Tools & Service Test Carts.zip"
)

PAD_BUTTONS = ("up", "down", "left", "right", "1", "2")

NOTHING_TO_RUN = 2

USAGE_ERROR = 3

INDENT = 2

USAGE = "usage: python3 -m conformance.testroms [--write] [image, folder or zip ...]"

CARTRIDGE_RAM = 0x8000

NAME_TABLE_BITS = 0x0E

NAME_TABLE_SHIFT = 10

ROWS = 24

COLUMNS = 32

INDEX_HIGH = 0x01

PRINTABLE = range(0x20, 0x7F)


def record(where: Path | str | None = None) -> dict[str, Any]:
    held = json.loads(Path(where or RECORD).read_text())
    assert isinstance(held, dict), "the record does not hold an object"
    return held


def entry(name: str, where: Path | str | None = None) -> dict[str, Any]:
    found = [one for one in record(where)["cartridges"] if one["id"] == name]
    assert found, f"{name} is not in the record"
    return dict(found[0])


def candidates(place: Path) -> Iterator[bytes]:
    if place.is_dir():
        for path in sorted(place.rglob("*")):
            yield from candidates(path)
    elif zipfile.is_zipfile(place):
        with zipfile.ZipFile(place) as archive:
            for member in archive.namelist():
                yield archive.read(member)
    elif place.is_file():
        yield place.read_bytes()


def images(places: Sequence[Path], wanted: set[str]) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    for place in places:
        for data in candidates(place):
            digest = hashlib.sha256(data).hexdigest()
            if digest in wanted:
                found[digest] = data
    return found


def reported(row: str) -> bool:
    text = row.strip()
    return any(character.isalnum() for character in text) and len(set(text)) > 1


def machine_for(image: bytes, plan: dict[str, Any]) -> segasms.Machine:
    cartridge = smsmapper.Cartridge(image, ram=CARTRIDGE_RAM)
    machine = segasms.Machine(plan["model"], cartridge=cartridge, region=plan["region"])
    return machine.reset().handed_over()


def _character(code: int) -> str:
    return chr(code) if code in PRINTABLE else " "


def screen(machine: segasms.Machine, offset: int) -> list[str]:
    vram = machine.vdp.memory
    base = (machine.vdp.registers[2] & NAME_TABLE_BITS) << NAME_TABLE_SHIFT
    rows = []
    for row in range(ROWS):
        cells = []
        for column in range(COLUMNS):
            at = base + (row * COLUMNS + column) * 2
            tile = vram.read8(at) | (vram.read8(at + 1) & INDEX_HIGH) << 8
            cells.append(_character(tile - offset))
        rows.append("".join(cells))
    return rows


def hold(machine: segasms.Machine, pad: int) -> None:
    for bit, button in enumerate(PAD_BUTTONS):
        if pad >> bit & 1:
            machine.release(button)
        else:
            machine.press(button)


def ran(image: bytes, plan: dict[str, Any]) -> dict[str, Any]:
    machine = machine_for(image, plan)
    seen: list[str] = []
    last = ""
    for frames, pad in plan["script"]:
        hold(machine, pad)
        for _ in range(frames):
            last = machine.run_frame().digest()
        shown = [row.strip() for row in screen(machine, plan["offset"]) if reported(row)]
        seen = list(dict.fromkeys([*seen, *shown]))
    return {"verdict": seen, "frame": last}


def measured(image: bytes, one: dict[str, Any]) -> list[dict[str, Any]]:
    return [{**plan, **ran(image, plan)} for plan in one["runs"]]


def options(argv: Sequence[str]) -> tuple[bool, list[Path]] | None:
    write = "--write" in argv
    rest = [one for one in argv if one != "--write"]
    if any(one.startswith("--") for one in rest):
        return None
    return write, [Path(one) for one in rest]


def places_from(given: list[Path], kept: Path) -> list[Path]:
    if given:
        return given
    named = os.environ.get(PLACES, "")
    return [Path(one) for one in named.split(os.pathsep) if one] or [kept]


def judged(one: dict[str, Any], found: list[dict[str, Any]]) -> bool:
    same = bool(found == one["runs"])
    print(f"{'ran' if same else 'DIFFERS'} {one['id']}: {len(found)} runs")
    for plan in found:
        print(
            f"  {plan['model']} {plan['region']}: {len(plan['verdict'])} lines, last frame {plan['frame'][:16]}"
        )
        for line in plan["verdict"]:
            print(f"    {line}")
    return same


def main(argv: Sequence[str], where: Path | str | None = None, kept: Path = KEPT) -> int:
    parsed = options(argv)
    if parsed is None:
        print(USAGE)
        return USAGE_ERROR
    write, given = parsed
    held = record(where)
    wanted = [one for one in held["cartridges"] if one["outcome"] == "run"]
    found = images(places_from(given, kept), {one["sha256"] for one in wanted})
    if not found:
        print(f"SKIPPED none of the {len(wanted)} pinned images is on this machine")
        return NOTHING_TO_RUN
    good = True
    for one in wanted:
        if one["sha256"] not in found:
            print(f"SKIPPED {one['id']}: not on this machine")
            continue
        result = measured(found[one["sha256"]], one)
        good = judged(one, result) and good
        one["runs"] = result
    if write:
        Path(where or RECORD).write_text(json.dumps(held, indent=INDENT) + "\n")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
