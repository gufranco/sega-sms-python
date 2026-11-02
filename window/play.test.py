import contextlib
import io
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pygame

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import segasms  # noqa: E402
from segasms import record  # noqa: E402
from window import play  # noqa: E402

MODE_4 = (0x3E, 0x04, 0xD3, 0xBF, 0x3E, 0x80, 0xD3, 0xBF)

BACKDROP_IS_ENTRY_1 = (0x3E, 0x01, 0xD3, 0xBF, 0x3E, 0x87, 0xD3, 0xBF)

ADDRESS_CRAM_17 = (0x3E, 0x11, 0xD3, 0xBF, 0x3E, 0xC0, 0xD3, 0xBF)

WRITE_3F_AND_LOOP = (0x3E, 0x3F, 0xD3, 0xBE, 0x18, 0xFE)

WHITE = bytes((*MODE_4, *BACKDROP_IS_ENTRY_1, *ADDRESS_CRAM_17, *WRITE_3F_AND_LOOP))

READ_PORT_DC = bytes([0xDB, 0xDC, 0x18, 0xFE])


def image(code: bytes) -> bytes:
    return code + bytes(0x8000 - len(code))


def kept(name: str) -> Path:
    where = Path(tempfile.mkdtemp()) / name
    where.write_bytes(image(WHITE))
    return where


def machine(code: bytes) -> segasms.Machine:
    return record.start(image(code), "sms", "sega")


def key(kind: int, pressed: int) -> pygame.event.Event:
    return pygame.event.Event(kind, key=pressed)


def closed_window() -> None:
    pygame.init()
    pygame.display.set_mode((1, 1))
    pygame.event.post(pygame.event.Event(pygame.QUIT))


def run_main(argv: list[str]) -> tuple[int, str]:
    with contextlib.redirect_stdout(io.StringIO()) as said:
        code = play.main(argv)
    return code, said.getvalue()


class ButtonTest(unittest.TestCase):
    def test_return_is_pause_on_a_console_and_start_on_a_game_gear(self) -> None:
        # Arrange
        handhelds = (False, True)

        # Act
        found = [play.button(pygame.K_RETURN, handheld) for handheld in handhelds]

        # Assert
        self.assertEqual(found, ["pause", "start"])

    def test_the_arrows_z_x_and_backspace_are_the_pad_and_reset(self) -> None:
        # Arrange
        keys = (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT, pygame.K_z)
        more = (pygame.K_x, pygame.K_BACKSPACE, pygame.K_q)

        # Act
        found = [play.button(one, handheld=False) for one in (*keys, *more)]

        # Assert
        self.assertEqual(found, ["up", "down", "left", "right", "1", "2", "reset", None])


class HandledTest(unittest.TestCase):
    def test_a_held_arrow_reaches_the_controller_port(self) -> None:
        # Arrange
        running = machine(READ_PORT_DC)
        events = [key(pygame.KEYDOWN, pygame.K_UP)]

        # Act
        going = play.handled(events, running)

        # Assert
        running.step()
        self.assertEqual((going, running.cpu.registers.a), (True, 0xFE))

    def test_a_released_arrow_leaves_the_controller_port(self) -> None:
        # Arrange
        running = machine(READ_PORT_DC)
        events = [key(pygame.KEYDOWN, pygame.K_UP), key(pygame.KEYUP, pygame.K_UP)]

        # Act
        play.handled(events, running)

        # Assert
        running.step()
        self.assertEqual(running.cpu.registers.a, 0xFF)

    def test_a_key_the_console_has_no_button_for_is_ignored(self) -> None:
        # Arrange
        running = machine(READ_PORT_DC)
        events = [key(pygame.KEYDOWN, pygame.K_q), pygame.event.Event(pygame.MOUSEMOTION)]

        # Act
        going = play.handled(events, running)

        # Assert
        running.step()
        self.assertEqual((going, running.cpu.registers.a), (True, 0xFF))

    def test_escape_and_closing_the_window_stop_the_run(self) -> None:
        # Arrange
        stops = ([key(pygame.KEYDOWN, pygame.K_ESCAPE)], [pygame.event.Event(pygame.QUIT)])

        # Act
        found = [play.handled(events, machine(READ_PORT_DC)) for events in stops]

        # Assert
        self.assertEqual(found, [False, False])


class ShowTest(unittest.TestCase):
    def test_a_frame_fills_the_window_at_its_scale(self) -> None:
        # Arrange
        pygame.init()
        white = segasms.Frame((0x3F,) * (256 * 192), width=256, height=192)

        # Act
        window = play.show(None, white, handheld=False, scale=2)

        # Assert
        self.assertEqual(
            (window.get_size(), tuple(window.get_at((511, 383)))[:3]),
            ((512, 384), (255, 255, 255)),
        )

    def test_a_frame_of_the_same_size_keeps_the_window(self) -> None:
        # Arrange
        pygame.init()
        white = segasms.Frame((0x3F,) * (160 * 144), width=160, height=144)
        first = play.show(None, white, handheld=True, scale=1)

        # Act
        second = play.show(first, white, handheld=True, scale=1)

        # Assert
        self.assertIs(second, first)


class MainTest(unittest.TestCase):
    def test_a_live_run_plays_the_frames_it_was_given(self) -> None:
        # Arrange
        rom = kept("white.sms")

        # Act
        found = run_main([str(rom), "--frames", "3"])

        # Assert
        self.assertEqual(found, (0, "played 3 frames\n"))

    def test_a_replay_emulates_first_then_plays_every_frame(self) -> None:
        # Arrange
        rom = kept("white.gg")

        # Act
        found = run_main([str(rom), "--replay", "3", "--scale", "1"])

        # Assert
        self.assertEqual(found, (0, "emulated 3 frames\nplayed 3 frames\n"))

    def test_a_window_closed_before_the_first_frame_plays_none(self) -> None:
        # Arrange
        rom = kept("white.sms")
        closed_window()

        # Act
        found = run_main([str(rom), "--frames", "3"])

        # Assert
        self.assertEqual(found, (0, "played 0 frames\n"))

    def test_a_replay_closed_before_the_first_frame_plays_none(self) -> None:
        # Arrange
        rom = kept("white.sms")
        closed_window()

        # Act
        found = run_main([str(rom), "--replay", "2"])

        # Assert
        self.assertEqual(found, (0, "emulated 2 frames\nplayed 0 frames\n"))

    def test_a_scale_that_is_not_a_positive_number_prints_the_usage(self) -> None:
        # Arrange
        argv = ["game.sms", "--scale", "0"]

        # Act
        found = run_main(argv)

        # Assert
        self.assertEqual(found, (2, play.USAGE + "\n"))

    def test_an_image_that_is_not_there_is_named(self) -> None:
        # Arrange
        missing = Path(tempfile.mkdtemp()) / "gone.gg"

        # Act
        found = run_main([str(missing)])

        # Assert
        self.assertEqual(found, (2, f"play: cannot read {missing}.\n"))


class ScriptTest(unittest.TestCase):
    def test_run_as_a_script_with_no_image_it_prints_the_usage(self) -> None:
        # Arrange
        script = ROOT / "window" / "play.py"

        # Act
        with (
            mock.patch.object(sys, "argv", [str(script)]),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as ended,
        ):
            runpy.run_path(str(script), run_name="__main__")

        # Assert
        self.assertEqual(ended.exception.code, 2)


unittest.main()
