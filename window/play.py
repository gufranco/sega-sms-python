from __future__ import annotations

import sys
import time
from collections.abc import Iterable, Sequence

import pygame

from segasms import record
from segasms.frame import Frame
from segasms.machine import PROCESSOR_HZ, Machine
from segasms.speaker import RATE

FRAMES = "--frames"

REPLAY = "--replay"

SCALE = "--scale"

DEFAULTS = {
    FRAMES: "216000",
    record.BOARD: record.DEFAULTS[record.BOARD],
    record.BIOS: record.DEFAULTS[record.BIOS],
    record.MODE: record.DEFAULTS[record.MODE],
    REPLAY: "",
    SCALE: "3",
}

COUNTS = (FRAMES, REPLAY, SCALE)

USAGE = (
    "usage: python3 -m window.play <image.sms|image.gg>"
    " [--board NAME] [--bios FILE] [--mode own|master-system]"
    " [--frames N] [--replay N] [--scale N]"
)

PLAY = record.Command("play", USAGE, DEFAULTS, COUNTS)

TITLE = "segasms"

SIGNED_16_BITS = -16

STEREO = 2

MILLISECONDS = 1000

KEYS = {
    pygame.K_UP: "up",
    pygame.K_DOWN: "down",
    pygame.K_LEFT: "left",
    pygame.K_RIGHT: "right",
    pygame.K_z: "1",
    pygame.K_x: "2",
    pygame.K_BACKSPACE: "reset",
}

CONSOLE_KEY = pygame.K_RETURN

STOP_KEY = pygame.K_ESCAPE

PRESSES = {pygame.KEYDOWN: True, pygame.KEYUP: False}


def button(key: int, handheld: bool) -> str | None:
    if key == CONSOLE_KEY:
        return "start" if handheld else "pause"
    return KEYS.get(key)


def stops(event: pygame.event.Event) -> bool:
    return event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == STOP_KEY)


def _press(event: pygame.event.Event, machine: Machine) -> None:
    if event.type not in PRESSES:
        return
    named = button(event.key, machine.console.model.handheld)
    if named is None:
        return
    if PRESSES[event.type]:
        machine.press(named)
    else:
        machine.release(named)


def handled(events: Iterable[pygame.event.Event], machine: Machine) -> bool:
    for event in events:
        if stops(event):
            return False
        _press(event, machine)
    return True


def show(window: pygame.Surface | None, shown: Frame, handheld: bool, scale: int) -> pygame.Surface:
    size = (shown.width * scale, shown.height * scale)
    target = window if window is not None and window.get_size() == size else None
    if target is None:
        target = pygame.display.set_mode(size)
    raw = record.picture(shown, handheld)
    surface = pygame.image.frombuffer(raw, (shown.width, shown.height), "RGB")
    target.blit(pygame.transform.scale(surface, size), (0, 0))
    pygame.display.flip()
    return target


def sound(samples: Sequence[int]) -> pygame.mixer.Sound:
    return pygame.mixer.Sound(buffer=record.pcm(samples))


def live(machine: Machine, scale: int, frames: int) -> int:
    channel = pygame.mixer.Channel(0)
    handheld = machine.console.model.handheld
    window: pygame.Surface | None = None
    for played in range(frames):
        if not handled(pygame.event.get(), machine):
            return played
        window = show(window, record.shown_by(machine), handheld, scale)
        channel.queue(sound(machine.speaker.take()))
    return frames


def replay(made: record.Recording, scale: int) -> int:
    window: pygame.Surface | None = None
    due = 0.0
    sound(made.samples).play()
    began = time.monotonic()
    for played, (shown, states) in enumerate(zip(made.frames, made.lengths, strict=True)):
        if any(stops(event) for event in pygame.event.get()):
            return played
        window = show(window, shown, made.handheld, scale)
        due += states / PROCESSOR_HZ
        pygame.time.wait(max(0, round((began + due - time.monotonic()) * MILLISECONDS)))
    return len(made.frames)


def _opened(caption: str) -> None:
    pygame.init()
    pygame.mixer.init(frequency=RATE, size=SIGNED_16_BITS, channels=STEREO, allowedchanges=0)
    pygame.display.set_caption(f"{TITLE}: {caption}")


def main(argv: Sequence[str]) -> int:
    begun = record.started(argv, PLAY)
    if isinstance(begun, str):
        sys.stdout.write(begun)
        return 2
    path, options, machine = begun
    scale = int(options[SCALE])
    _opened(path.name)
    if options[REPLAY]:
        made = record.record(machine, int(options[REPLAY]))
        sys.stdout.write(f"emulated {len(made.frames)} frames\n")
        played = replay(made, scale)
    else:
        played = live(machine, scale, int(options[FRAMES]))
    pygame.quit()
    sys.stdout.write(f"played {played} frames\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
