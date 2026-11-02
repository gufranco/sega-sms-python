from __future__ import annotations

from collections.abc import Callable
from typing import Any

from smsmapper import ports
from smsmapper.console import Console

VDP_TARGETS = frozenset(
    {ports.V_COUNTER, ports.H_COUNTER, ports.SOUND, ports.VDP_DATA, ports.VDP_CONTROL}
)

STEREO = f"{ports.HANDHELD}6"

LOW_BYTE = 0xFF


class Memory:
    __slots__ = ("console",)

    def __init__(self, console: Console) -> None:
        self.console = console

    def read8(self, address: int) -> int:
        return self.console.read(address)

    def write8(self, address: int, value: int) -> None:
        self.console.write(address, value)


def at_once() -> None:
    return None


class Ports:
    __slots__ = ("console", "strobe", "vdp")

    def __init__(self, console: Console, vdp: Any, strobe: Callable[[], None] = at_once) -> None:
        self.console = console
        self.vdp = vdp
        self.strobe = strobe

    def target(self, port: int, direction: str) -> str:
        return ports.decode(self.console.decoding(), port, direction)

    def read(self, port: int) -> int:
        self.strobe()
        if self.target(port, ports.READ) in VDP_TARGETS:
            read: int = self.vdp.read_port(port & LOW_BYTE)
            return read
        return self.console.read_port(port)

    def write(self, port: int, value: int) -> None:
        self.strobe()
        target = self.target(port, ports.WRITE)
        if target in VDP_TARGETS:
            self.vdp.write_port(port & LOW_BYTE, value)
            return
        latches = self.console.latches
        self.console.write_port(port, value)
        if target == STEREO:
            self.vdp.sound.write_stereo(value)
        if self.console.latches != latches:
            self.vdp.latch_h_counter()
