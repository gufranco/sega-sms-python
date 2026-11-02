from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

ACTIVE = "active"

WIDTH = 256

WORD = 2

TICKS_PER_DOT = 2

WINDOW_LEFT = 48

WINDOW_TOP = 24

WINDOW_WIDTH = 160

WINDOW_HEIGHT = 144


@dataclass(frozen=True, slots=True)
class Frame:
    colours: tuple[int, ...]
    width: int
    height: int

    def digest(self) -> str:
        packed = b"".join(colour.to_bytes(WORD, "big") for colour in self.colours)
        return hashlib.sha256(packed).hexdigest()


def window(whole: Frame) -> Frame:
    starts = (
        row * whole.width + WINDOW_LEFT for row in range(WINDOW_TOP, WINDOW_TOP + WINDOW_HEIGHT)
    )
    colours = tuple(colour for at in starts for colour in whole.colours[at : at + WINDOW_WIDTH])
    return Frame(colours, WINDOW_WIDTH, WINDOW_HEIGHT)


class Beam(Protocol):
    cycles: int
    line: int
    dot: int
    shown: str
    colour: int | None


class Screen:
    __slots__ = ("dots", "finished", "start")

    def __init__(self, start: int = 0) -> None:
        self.dots: list[int] = []
        self.finished: Frame | None = None
        self.start = start

    def watch(self, vdp: Beam) -> None:
        if (vdp.cycles - self.start) % TICKS_PER_DOT:
            return
        if vdp.shown == ACTIVE and vdp.colour is not None:
            self.dots.append(vdp.colour)
        if (vdp.line, vdp.dot) == (0, 0):
            self.finished = Frame(tuple(self.dots), WIDTH, len(self.dots) // WIDTH)
            self.dots = []

    def take(self) -> Frame | None:
        finished, self.finished = self.finished, None
        return finished
