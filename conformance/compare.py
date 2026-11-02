import hashlib
import struct
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path

import smsmapper

import segasms
from conformance import census
from segasms import frame

FRAMER = "gpgx-frames"

HEADER = struct.Struct("<HH")

SKIPPED = 5

FRAMES = 60

USAGE = "usage: python3 -m conformance.compare <image.sms|image.gg> [...] [--frames N]"

Frames = list[tuple[int, ...]]


def pixel(word: int, handheld: bool) -> int:
    if handheld:
        red, green, blue = word & 0x0F, (word >> 4) & 0x0F, (word >> 8) & 0x0F
    else:
        red, green, blue = (
            (level << 2) | level for level in (word & 3, (word >> 2) & 3, (word >> 4) & 3)
        )
    return red << 12 | (red >> 3) << 11 | green << 7 | (green >> 2) << 5 | blue << 1 | blue >> 3


def ours(image: bytes, console: str, frames: int) -> Frames:
    model, handheld_mode = census.MODELS[console]
    cartridge = smsmapper.Cartridge(image)
    built = segasms.Machine(model, cartridge=cartridge, cleared=True, handheld_mode=handheld_mode)
    machine = built.reset()
    handheld = machine.console.model.handheld
    found = []
    for _ in range(frames):
        drawn = machine.run_frame()
        shown = frame.window(drawn) if machine.windowed() else drawn
        found.append(tuple(pixel(colour, handheld) for colour in shown.colours))
    return found


def theirs(image: bytes, suffix: str, frames: int) -> Frames:
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / f"image{suffix}"
        path.write_bytes(image)
        out = subprocess.run(
            [FRAMER, str(path), str(frames)], capture_output=True, check=True
        ).stdout
    found = []
    at = 0
    while at < len(out):
        width, height = HEADER.unpack_from(out, at)
        at += HEADER.size
        found.append(struct.unpack_from(f"<{width * height}H", out, at))
        at += width * height * 2
    return found


OFFSETS = (0, 1, -1)

STEP = {0: "in step", 1: "theirs a frame ahead", -1: "ours a frame ahead"}

Alignment = tuple[int, int | None, int]


def aligned(
    mine: Sequence[tuple[int, ...]], other: Sequence[tuple[int, ...]], skipped: int = SKIPPED
) -> Alignment:
    best: Alignment | None = None
    for offset in OFFSETS:
        compared = range(skipped + 1, min(len(mine), len(other)) - 1)
        differing = [k for k in compared if mine[k] != other[k + offset]]
        found = (offset, differing[0] if differing else None, len(differing))
        if best is None or found[2] < best[2]:
            best = found
    assert best is not None, "no offset was tried"
    return best


def _options(argv: Sequence[str]) -> tuple[list[Path], int] | None:
    paths: list[Path] = []
    frames = FRAMES
    rest = list(argv)
    while rest:
        item = rest.pop(0)
        if item == "--frames" and rest:
            frames = int(rest.pop(0))
        elif not item.startswith("--"):
            paths.append(Path(item))
    return (paths, frames) if paths else None


def main(argv: Sequence[str], ours: Callable[[bytes, str, int], Frames] = ours) -> int:
    chosen = _options(argv)
    if chosen is None:
        print(USAGE)
        return 2
    paths, frames = chosen
    compared: set[str] = set()
    pinned = census.sms_mode()
    differ = 0
    for path in paths:
        for _, name, image in census.images_in(path):
            digest = hashlib.sha256(image).hexdigest()
            if digest in compared:
                continue
            compared.add(digest)
            suffix = Path(name).suffix.lower()
            console = census.console_of(image, name, pinned)
            offset, found, count = aligned(
                ours(image, console, frames), theirs(image, suffix, frames)
            )
            if found is None:
                print(f"same {name}: {frames} frames, {STEP[offset]}")
            else:
                print(f"DIFFERS {name}: {count} frames from frame {found}, {STEP[offset]}")
                differ += 1
    print(f"{len(compared)} images, {len(compared) - differ} the same, {differ} differ")
    return 1 if differ else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
