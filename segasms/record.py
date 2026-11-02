from __future__ import annotations

import fractions
import io
import struct
import sys
import wave
import zlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import smsmapper

from segasms import frame
from segasms.frame import Frame
from segasms.machine import PROCESSOR_HZ, Machine
from segasms.speaker import RATE

MODELS = {".sms": "sms", ".gg": "gg"}

BOARD = "--board"

BIOS = "--bios"

FRAMES = "--frames"

OUT = "--out"

MODE = "--mode"

OWN_MODE = "own"

MASTER_SYSTEM_MODE = "master-system"

MODES = (OWN_MODE, MASTER_SYSTEM_MODE)

HANDHELD_MODEL = "gg"

DEFAULTS = {FRAMES: "300", BOARD: "sega", BIOS: "", MODE: OWN_MODE, OUT: "recordings"}

COUNTS = (FRAMES,)

USAGE = (
    "usage: python3 -m segasms.record <image.sms|image.gg>"
    " [--frames N] [--board NAME] [--bios FILE] [--mode own|master-system] [--out FOLDER]"
)

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

DEPTH = 8

TRUECOLOUR = 2

LOOP_FOREVER = 0

NO_FILTER = b"\x00"

LONGEST_DENOMINATOR = 0xFFFF

STEREO = 2

SAMPLE_BYTES = 2

CONSOLE_STEP = 0x55

HANDHELD_STEP = 0x11

CONSOLE_SHIFTS = (0, 2, 4)

HANDHELD_SHIFTS = (0, 4, 8)

Options = tuple[Path, dict[str, str]]

Started = tuple[Path, dict[str, str], Machine]


@dataclass(frozen=True, slots=True)
class Recording:
    frames: tuple[Frame, ...]
    lengths: tuple[int, ...]
    samples: tuple[int, ...]
    handheld: bool


def rgb(colour: int, handheld: bool) -> bytes:
    if handheld:
        return bytes(((colour >> shift) & 0x0F) * HANDHELD_STEP for shift in HANDHELD_SHIFTS)
    return bytes(((colour >> shift) & 0x03) * CONSOLE_STEP for shift in CONSOLE_SHIFTS)


def picture(shown: Frame, handheld: bool) -> bytes:
    colours = {colour: rgb(colour, handheld) for colour in set(shown.colours)}
    return b"".join(colours[one] for one in shown.colours)


def delay(states: int) -> tuple[int, int]:
    lasted = fractions.Fraction(states, PROCESSOR_HZ).limit_denominator(LONGEST_DENOMINATOR)
    return lasted.numerator, lasted.denominator


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def _pixels(shown: Frame, handheld: bool) -> bytes:
    raw = picture(shown, handheld)
    stride = shown.width * len(rgb(0, handheld))
    rows = range(0, len(raw), stride)
    return zlib.compress(b"".join(NO_FILTER + raw[at : at + stride] for at in rows))


def _control(sequence: int, shown: Frame, states: int) -> bytes:
    numerator, denominator = delay(states)
    fields = (sequence, shown.width, shown.height, 0, 0, numerator, denominator, 0, 0)
    return chunk(b"fcTL", struct.pack(">IIIIIHHBB", *fields))


def animated_png(made: Recording) -> bytes:
    first = made.frames[0]
    header = struct.pack(">IIBBBBB", first.width, first.height, DEPTH, TRUECOLOUR, 0, 0, 0)
    parts = [PNG_SIGNATURE, chunk(b"IHDR", header)]
    parts.append(chunk(b"acTL", struct.pack(">II", len(made.frames), LOOP_FOREVER)))
    sequence = 0
    for index, (shown, states) in enumerate(zip(made.frames, made.lengths, strict=True)):
        parts.append(_control(sequence, shown, states))
        data = _pixels(shown, made.handheld)
        if index == 0:
            parts.append(chunk(b"IDAT", data))
            sequence += 1
        else:
            parts.append(chunk(b"fdAT", struct.pack(">I", sequence + 1) + data))
            sequence += 2
    parts.append(chunk(b"IEND", b""))
    return b"".join(parts)


def pcm(samples: Sequence[int]) -> bytes:
    return struct.pack(f"<{len(samples)}h", *samples)


def wav(samples: Sequence[int], rate: int = RATE) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(STEREO)
        out.setsampwidth(SAMPLE_BYTES)
        out.setframerate(rate)
        out.writeframes(pcm(samples))
    return buffer.getvalue()


def start(
    image: bytes, model: str, board: str, bios: bytes | None = None, *, handheld_mode: bool = True
) -> Machine:
    cartridge = smsmapper.Cartridge(image, board=board)
    if bios is None:
        built = Machine(model, cartridge=cartridge, handheld_mode=handheld_mode)
        return built.reset().handed_over()
    boot = smsmapper.Cartridge(bios)
    return Machine(model, cartridge=cartridge, bios=boot, handheld_mode=handheld_mode).reset()


def console(path: Path, mode: str) -> tuple[str, bool]:
    if mode == MASTER_SYSTEM_MODE:
        return HANDHELD_MODEL, False
    return MODELS[path.suffix.lower()], True


def shown_by(machine: Machine) -> Frame:
    drawn = machine.run_frame()
    return frame.window(drawn) if machine.windowed() else drawn


def record(machine: Machine, frames: int) -> Recording:
    shown: list[Frame] = []
    lengths: list[int] = []
    for _ in range(frames):
        before = machine.cpu.cycles
        shown.append(shown_by(machine))
        lengths.append(machine.cpu.cycles - before)
    handheld = machine.console.model.handheld
    return Recording(tuple(shown), tuple(lengths), machine.speaker.take(), handheld)


def counted(text: str) -> bool:
    return text.isdigit() and int(text) >= 1


def parsed(
    argv: Sequence[str], defaults: Mapping[str, str], counts: Sequence[str]
) -> Options | None:
    paths: list[Path] = []
    chosen = dict(defaults)
    rest = list(argv)
    while rest:
        item = rest.pop(0)
        if item in chosen and rest:
            chosen[item] = rest.pop(0)
        else:
            paths.append(Path(item))
    if len(paths) != 1 or paths[0].suffix.lower() not in MODELS:
        return None
    numbers = all(counted(chosen[name]) for name in counts if chosen[name])
    known = chosen[BOARD] in smsmapper.BOARDS and chosen[MODE] in MODES
    return (paths[0], chosen) if numbers and known else None


def opened(path: Path, bios: str, tool: str) -> tuple[bytes, bytes | None] | str:
    wanted = [path, *([Path(bios)] if bios else [])]
    missing = [one for one in wanted if not one.is_file()]
    if missing:
        return f"{tool}: cannot read {missing[0]}.\n"
    return path.read_bytes(), Path(bios).read_bytes() if bios else None


@dataclass(frozen=True, slots=True)
class Command:
    tool: str
    usage: str
    defaults: Mapping[str, str]
    counts: Sequence[str]


RECORD = Command("record", USAGE, DEFAULTS, COUNTS)


def started(argv: Sequence[str], command: Command) -> Started | str:
    chosen = parsed(argv, command.defaults, command.counts)
    if chosen is None:
        return command.usage + "\n"
    path, options = chosen
    images = opened(path, options[BIOS], command.tool)
    if isinstance(images, str):
        return images
    model, handheld_mode = console(path, options[MODE])
    machine = start(images[0], model, options[BOARD], images[1], handheld_mode=handheld_mode)
    return path, options, machine


def main(argv: Sequence[str]) -> int:
    begun = started(argv, RECORD)
    if isinstance(begun, str):
        sys.stdout.write(begun)
        return 2
    path, options, machine = begun
    made = record(machine, int(options[FRAMES]))
    out = Path(options[OUT])
    out.mkdir(parents=True, exist_ok=True)
    picture_path, sound_path = out / f"{path.stem}.png", out / f"{path.stem}.wav"
    picture_path.write_bytes(animated_png(made))
    sound_path.write_bytes(wav(made.samples))
    sys.stdout.write(f"{picture_path}: {len(made.frames)} frames\n")
    sys.stdout.write(f"{sound_path}: {len(made.samples) // STEREO} samples at {RATE} Hz\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
