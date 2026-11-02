from __future__ import annotations

import collections
import hashlib
import json
import sys
import zipfile
from collections.abc import Iterator, Mapping, Sequence
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import smsmapper  # noqa: E402

import segasms  # noqa: E402

CONSOLE = ".sms"

HANDHELD = ".gg"

SUFFIXES = (CONSOLE, HANDHELD)

SMS_MODE = "sms mode"

MODELS = {CONSOLE: ("sms", True), HANDHELD: ("gg", True), SMS_MODE: ("gg", False)}

EUROPEAN_SET = "Europe - A-Z"

GATED_SETS = ("US - A-Z", EUROPEAN_SET, "Japan - A-Z")

PAL_REGION = "europe"

NTSC_REGION = "usa"

NOT_GAMES = ("[BIOS]", "(Beta", "(Proto", "(Demo", "(Sample")

FRAMES = 300

JOBS = 10

DEFAULT_BOARD = "sega"

BOARDS = ROOT / "sms-mapper-python" / "conformance" / "boards.json"

CORPUS = Path(__file__).resolve().parent / "corpus.json"

CORPUS_INDENT = 2

RAISES_NOTHING = "the machine raises on no image"

DRAWS = "every retail image draws more than one colour within the frame bound"

PROPERTIES = (RAISES_NOTHING, DRAWS)

BLANK = "images other than retail ones that never draw more than one colour"

OBSERVED = (BLANK,)

USAGE = "usage: python3 -m conformance.census <path> [path ...] [--frames N] [--jobs N]"

Image = tuple[str, str, bytes]

Job = tuple[bytes, int, str, str, str]

Distinct = tuple[bool, bytes, str, str, str]


def boards(where: Path = BOARDS) -> dict[str, str]:
    held = json.loads(where.read_text())["boards"]
    return {str(one["sha1"]): str(one["board"]) for one in held}


def sms_mode(where: Path = BOARDS) -> frozenset[str]:
    held = json.loads(where.read_text())["smsMode"]
    return frozenset(str(one["sha1"]) for one in held)


def console_of(rom: bytes, name: str, pinned: frozenset[str]) -> str:
    if hashlib.sha1(rom, usedforsecurity=False).hexdigest() in pinned:
        return SMS_MODE
    return _suffix(name)


def _members(where: Path) -> Iterator[Image]:
    with zipfile.ZipFile(where) as bundle:
        for entry in bundle.infolist():
            if not entry.is_dir() and Path(entry.filename).suffix.lower() in SUFFIXES:
                yield where.name, Path(entry.filename).name, bundle.read(entry)


def images_in(where: Path) -> Iterator[Image]:
    if where.is_dir():
        for path in sorted(where.iterdir()):
            yield from images_in(path)
        return
    if where.suffix.lower() == ".zip":
        yield from _members(where)
    elif where.suffix.lower() in SUFFIXES:
        yield where.parent.name, where.name, where.read_bytes()


def gated(collection: str, name: str) -> bool:
    retail = any(one in collection for one in GATED_SETS)
    return retail and not any(tag in name for tag in NOT_GAMES)


def board_of(rom: bytes, listed: Mapping[str, str]) -> str:
    found = listed.get(hashlib.sha1(rom, usedforsecurity=False).hexdigest(), DEFAULT_BOARD)
    return found if found in smsmapper.BOARDS else DEFAULT_BOARD


def _suffix(name: str) -> str:
    return HANDHELD if name.lower().endswith(HANDHELD) else CONSOLE


def build(job: Job) -> segasms.Machine:
    rom, _, console, board, region = job
    cartridge = smsmapper.Cartridge(rom, board=board)
    model, handheld_mode = MODELS[console]
    machine = segasms.Machine(
        model, cartridge=cartridge, region=region, handheld_mode=handheld_mode
    )
    return machine.reset().handed_over()


def examine(job: Job) -> dict[str, Any]:
    frames = job[1]
    drew: int | None = None
    chain = hashlib.sha256()
    shown = 0
    try:
        machine = build(job)
        for shown in range(frames):
            frame = machine.run_frame()
            chain.update(bytes.fromhex(frame.digest()))
            if drew is None and len(set(frame.colours)) > 1:
                drew = shown
    except Exception as error:
        return {
            "drew": drew,
            "chain": None,
            "raised": f"{type(error).__name__}: {error} at frame {shown}",
        }
    return {"drew": drew, "chain": chain.hexdigest(), "raised": None}


def _distinct(paths: Sequence[Path], listed: Mapping[str, str]) -> tuple[int, list[Distinct]]:
    count = 0
    held: dict[str, Distinct] = {}
    sets: dict[str, set[str]] = {}
    for where in paths:
        for collection, name, rom in images_in(where):
            count += 1
            digest = hashlib.sha256(rom).hexdigest()
            before = held.get(digest)
            retail = bool(before and before[0]) or gated(collection, name)
            found = sets.setdefault(digest, set())
            found |= {one for one in GATED_SETS if one in collection}
            region = PAL_REGION if found == {EUROPEAN_SET} else NTSC_REGION
            held[digest] = (retail, rom, name, board_of(rom, listed), region)
    return count, [held[digest] for digest in sorted(held)]


def _results(
    images: Sequence[Distinct], frames: int, jobs: int, pinned: frozenset[str]
) -> list[dict[str, Any]]:
    work = [
        (rom, frames, console_of(rom, name, pinned), board, region)
        for _, rom, name, board, region in images
    ]
    if jobs <= 1:
        return [examine(one) for one in work]
    with ProcessPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(examine, work))


def culprits(images: Sequence[Distinct], results: Sequence[dict[str, Any]]) -> dict[str, list[str]]:
    named: dict[str, list[str]] = {name: [] for name in (*PROPERTIES, *OBSERVED)}
    for (retail, _, name, _, _), found in zip(images, results, strict=True):
        if found["raised"] is not None:
            named[RAISES_NOTHING].append(f"{name}: {found['raised']}")
        elif found["drew"] is None:
            named[DRAWS if retail else BLANK].append(name)
    return named


def take(
    paths: Sequence[Path], frames: int = FRAMES, jobs: int = JOBS, listed: Path = BOARDS
) -> dict[str, Any]:
    count, images = _distinct(paths, boards(listed))
    results = _results(images, frames, jobs, sms_mode(listed))
    named = culprits(images, results)
    drew = collections.Counter(str(found["drew"]) for found in results if found["drew"] is not None)
    return {
        "listings": count,
        "images": len(images),
        "gated": sum(1 for image in images if image[0]),
        "frames": frames,
        "pal": sum(1 for image in images if image[4] == PAL_REGION),
        "properties": {name: len(named[name]) for name in PROPERTIES},
        "drew": dict(sorted(drew.items(), key=lambda item: int(item[0]))),
        "runs": {
            hashlib.sha256(image[1]).hexdigest(): [found["drew"], found["chain"]]
            for image, found in zip(images, results, strict=True)
        },
        "culprits": named,
    }


def _options(argv: Sequence[str]) -> tuple[list[Path], int, int] | None:
    paths: list[Path] = []
    frames, jobs = FRAMES, JOBS
    rest = list(argv)
    while rest:
        item = rest.pop(0)
        if item in ("--frames", "--jobs"):
            if not rest:
                return None
            value = int(rest.pop(0))
            frames, jobs = (value, jobs) if item == "--frames" else (frames, value)
        else:
            paths.append(Path(item))
    return (paths, frames, jobs) if paths else None


def report(taken: Mapping[str, Any]) -> list[str]:
    named = taken["culprits"]
    lines = [
        f"{taken['listings']} listings, {taken['images']} distinct images, "
        f"{taken['gated']} retail, {taken['frames']} frames each"
    ]
    for name, count in taken["properties"].items():
        lines.append(f"  {'ok  ' if not count else '   !'}  {name}: {count} broken")
        lines.extend(f"         {one}" for one in named[name])
    for name in OBSERVED:
        lines.append(f"  observed  {name}: {len(named[name])} images")
        lines.extend(f"         {one}" for one in named[name])
    return lines


def main(argv: Sequence[str], into: Path = CORPUS) -> int:
    chosen = _options(argv)
    if chosen is None:
        print(USAGE)
        return 2
    paths, frames, jobs = chosen
    for one in paths:
        if not one.exists():
            print(f"absent: {one}")
    taken = take([one for one in paths if one.exists()], frames, jobs)
    for line in report(taken):
        print(line)
    if taken["images"]:
        kept = {key: value for key, value in taken.items() if key != "culprits"}
        into.write_text(json.dumps(kept, indent=CORPUS_INDENT) + "\n")
    failed = any(taken["properties"].values()) or not taken["images"]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
