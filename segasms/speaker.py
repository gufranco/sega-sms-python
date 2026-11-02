from __future__ import annotations

from segavdp.sound import Generator

RATE = 44_100

CHANNELS = 4

FULL_SCALE = 32_767


def scaled(level: float) -> int:
    return round(level * FULL_SCALE / CHANNELS)


class Speaker:
    __slots__ = ("heard", "left", "periods", "phase", "rate", "right", "samples")

    def __init__(self, periods: int, rate: int = RATE) -> None:
        self.periods = periods
        self.rate = rate
        self.phase = 0
        self.heard = 0
        self.left = 0.0
        self.right = 0.0
        self.samples: list[int] = []

    def hear(self, voice: Generator) -> None:
        right, left = voice.sides
        for bit, gain, on_right, on_left in zip(voice.bits, voice.gains, right, left, strict=True):
            if bit:
                self.right += gain * on_right
                self.left += gain * on_left
        self.heard += 1
        self.phase += self.rate
        if self.phase >= self.periods:
            self.phase -= self.periods
            self.samples += (scaled(self.left / self.heard), scaled(self.right / self.heard))
            self.heard, self.left, self.right = 0, 0.0, 0.0

    def take(self) -> tuple[int, ...]:
        taken, self.samples = tuple(self.samples), []
        return taken
