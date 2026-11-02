import statistics
import sys
import time
from collections.abc import Sequence

import smsmapper

import segasms

MEASURED_HERE = 298_000

HEADROOM = 10

FLOOR_STEP = 1_000

FLOOR = MEASURED_HERE // HEADROOM // FLOOR_STEP * FLOOR_STEP

FRAMES = 2

REPEATS = 5

IMAGE_SIZE = 0x8000

MODE_4 = (0x3E, 0x04, 0xD3, 0xBF, 0x3E, 0x80, 0xD3, 0xBF)

DISPLAY_ON = (0x3E, 0x40, 0xD3, 0xBF, 0x3E, 0x81, 0xD3, 0xBF)

COUNTER_TO_VRAM_AND_RAM = (0xDB, 0x7E, 0xD3, 0xBE, 0x32, 0x00, 0xC0, 0x18, 0xF8)

BUSY = bytes((*MODE_4, *DISPLAY_ON, *COUNTER_TO_VRAM_AND_RAM))


def busy_machine() -> segasms.Machine:
    image = BUSY + bytes(IMAGE_SIZE - len(BUSY))
    return segasms.Machine("sms", cartridge=smsmapper.Cartridge(image)).reset()


class Timed:
    __slots__ = ("calls", "seconds", "what")

    def __init__(self, what: str, calls: int, seconds: Sequence[float]) -> None:
        self.what = what
        self.calls = calls
        self.seconds = list(seconds)

    def median(self) -> float:
        return statistics.median(self.seconds)

    def rate(self) -> float:
        taken = self.median()
        return self.calls / taken if taken > 0 else 0.0

    def beats(self, floor: int) -> bool:
        return self.rate() >= floor


def run(machine: segasms.Machine, frames: int) -> int:
    start = machine.cpu.cycles
    for _ in range(frames):
        machine.run_frame()
    spent: int = machine.cpu.cycles - start
    return spent


def measure(frames: int = FRAMES, repeats: int = REPEATS) -> Timed:
    seconds = []
    spent = 0
    for _ in range(repeats):
        machine = busy_machine()
        started = time.perf_counter()
        spent = run(machine, frames)
        seconds.append(time.perf_counter() - started)
    return Timed("T states through a running machine", spent, seconds)


def lines_for(found: Timed, floor: int = FLOOR) -> list[str]:
    runtime = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    lines = [
        f"  {found.what}: {found.rate():,.0f} per second"
        f" (median of {len(found.seconds)}) on Python {runtime}",
        f"  floor: {floor:,} per second",
    ]
    if not found.beats(floor):
        lines.append(f"  below the floor: {found.rate():,.0f} is under {floor:,}")
    return lines


def main(frames: int = FRAMES, repeats: int = REPEATS, floor: int = FLOOR) -> int:
    found = measure(frames, repeats)
    for line in lines_for(found, floor):
        print(line)
    return 0 if found.beats(floor) else 1


if __name__ == "__main__":
    raise SystemExit(main())
