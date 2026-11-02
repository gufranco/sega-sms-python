from __future__ import annotations

import segavdp
import z80
from smsmapper.boards import Board
from smsmapper.console import Console

from segasms import bus, models
from segasms.errors import NoFrame
from segasms.frame import Frame, Screen
from segasms.speaker import Speaker

TICKS_PER_T_STATE = 3

STROBE_TICKS = 10

FRAME_LIMIT = 100_000

COLOUR_ENTRIES = 32

REGISTER_WRITE = 0x80

PROCESSOR_HZ = 3_580_000

HANDED_OVER_STACK = 0xDFF0

MEMORY_CONTROL_COPY = 0xC000

HANDED_OVER_CONTROL = 0xAB


class Machine:
    __slots__ = ("cleared", "console", "cpu", "early", "lead", "screen", "speaker", "vdp")

    def __init__(
        self,
        model: str | None = None,
        cartridge: Board | None = None,
        bios: Board | None = None,
        region: str | None = None,
        *,
        cleared: bool = False,
        handheld_mode: bool = True,
    ) -> None:
        self.cleared = cleared
        self.early: list[bool] = []
        self.lead = 0
        self.console = Console(
            model, cartridge=cartridge, bios=bios, region=region, handheld_mode=handheld_mode
        )
        name = self.console.model.name
        self.vdp = segavdp.Chip(
            models.vdp_part(name),
            segavdp.Vram(fill=0) if cleared else None,
            region=models.vdp_region(name, self.console.region),
            handheld_mode=handheld_mode,
        )
        self.cpu = z80.Cpu(
            models.lookup(name).processor,
            bus.Memory(self.console),
            ports=bus.Ports(self.console, self.vdp, self.strobe),
        )
        self.cpu.on_cycle = self.cycle
        self.screen = Screen()
        self.speaker = self._speaker()

    def cycle(self) -> None:
        cpu = self.cpu
        if self.early:
            cpu.irq_line = self.early.pop()
        else:
            self._run(TICKS_PER_T_STATE - self.lead)
            self.lead = 0
            cpu.irq_line = self._closed()
        cpu.nmi_line = self.console.nmi

    def strobe(self) -> None:
        whole, self.lead = divmod(STROBE_TICKS, TICKS_PER_T_STATE)
        passed = []
        for _ in range(whole):
            self._run(TICKS_PER_T_STATE)
            passed.append(self._closed())
        self._run(self.lead)
        self.early = passed[::-1]

    def _run(self, ticks: int) -> None:
        vdp = self.vdp
        watch = self.screen.watch
        for _ in range(ticks):
            vdp.tick()
            watch(vdp)

    def _closed(self) -> bool:
        vdp = self.vdp
        if vdp.sound.phase == 0:
            self.speaker.hear(vdp.sound)
        return bool(vdp.interrupt)

    def reset(self) -> Machine:
        self.vdp.reset()
        if self.cleared:
            self._clear()
        self.screen = Screen(self.vdp.cycles)
        self.speaker = self._speaker()
        self.early = []
        self.lead = 0
        self.cpu.reset()
        return self

    def windowed(self) -> bool:
        return bool(self.vdp.handheld_mode)

    def handed_over(self) -> Machine:
        if not self.console.model.handheld:
            self.cpu.registers.sp = HANDED_OVER_STACK
            self.console.write(MEMORY_CONTROL_COPY, HANDED_OVER_CONTROL)
        return self

    def _speaker(self) -> Speaker:
        return Speaker(PROCESSOR_HZ // self.vdp.sound.part.prescale)

    def _clear(self) -> None:
        for index in range(COLOUR_ENTRIES):
            self.vdp.cram.write(index, 0, False)
        for register in range(len(self.vdp.registers)):
            self.vdp.write_control(0)
            self.vdp.write_control(REGISTER_WRITE | register)

    def step(self) -> int:
        spent: int = self.cpu.step()
        return spent

    def run_frame(self, limit: int = FRAME_LIMIT) -> Frame:
        for _ in range(limit):
            self.cpu.step()
            finished = self.screen.take()
            if finished is not None:
                return finished
        raise NoFrame(f"no frame finished within {limit} instructions")

    def press(self, button: str, player: int = 1) -> None:
        self.console.press(button, player)

    def release(self, button: str, player: int = 1) -> None:
        self.console.release(button, player)
