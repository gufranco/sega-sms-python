import hashlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import smsmapper  # noqa: E402

import segasms  # noqa: E402
from segasms import frame as screen  # noqa: E402

MODE_4 = (0x3E, 0x04, 0xD3, 0xBF, 0x3E, 0x80, 0xD3, 0xBF)

BACKDROP_IS_ENTRY_1 = (0x3E, 0x01, 0xD3, 0xBF, 0x3E, 0x87, 0xD3, 0xBF)

ADDRESS_CRAM_17 = (0x3E, 0x11, 0xD3, 0xBF, 0x3E, 0xC0, 0xD3, 0xBF)

WRITE_3F_AND_LOOP = (0x3E, 0x3F, 0xD3, 0xBE, 0x18, 0xFE)

BACKDROP_IN_CRAM_17 = bytes((*MODE_4, *BACKDROP_IS_ENTRY_1, *ADDRESS_CRAM_17, *WRITE_3F_AND_LOOP))


def machine_running(code: bytes) -> segasms.Machine:
    image = code + bytes(0x8000 - len(code))
    return segasms.Machine("sms", cartridge=smsmapper.Cartridge(image)).reset()


class FrameTest(unittest.TestCase):
    def test_a_frame_holds_every_active_dot(self) -> None:
        # Arrange
        machine = machine_running(BACKDROP_IN_CRAM_17)

        # Act
        frame = machine.run_frame()

        # Assert
        self.assertEqual((frame.width, frame.height, len(frame.colours)), (256, 192, 49152))

    def test_a_blanked_screen_shows_the_backdrop_colour_ram_names(self) -> None:
        # Arrange
        machine = machine_running(BACKDROP_IN_CRAM_17)
        machine.run_frame()

        # Act
        frame = machine.run_frame()

        # Assert
        self.assertEqual(set(frame.colours), {0x3F})

    def test_the_digest_is_sha_256_over_each_colour_as_two_bytes(self) -> None:
        # Arrange
        frame = segasms.Frame((0x3F, 0x00), width=2, height=1)

        # Act
        digest = frame.digest()

        # Assert
        self.assertEqual(digest, hashlib.sha256(bytes([0x00, 0x3F, 0x00, 0x00])).hexdigest())

    def test_one_dot_changed_changes_the_digest(self) -> None:
        # Arrange
        frames = [segasms.Frame(colours, width=2, height=1) for colours in ((1, 2), (1, 3))]

        # Act
        digests = {frame.digest() for frame in frames}

        # Assert
        self.assertEqual(len(digests), 2)

    def test_a_machine_that_never_finishes_a_frame_says_so(self) -> None:
        # Arrange
        machine = machine_running(bytes([0x18, 0xFE]))

        # Act
        with self.assertRaises(segasms.NoFrame) as caught:
            machine.run_frame(limit=10)

        # Assert
        self.assertIn("10 instructions", str(caught.exception))


class WindowTest(unittest.TestCase):
    def test_the_game_gear_window_is_the_middle_160_by_144_dots(self) -> None:
        # Arrange
        whole = segasms.Frame(tuple(range(256 * 192)), width=256, height=192)

        # Act
        shown = screen.window(whole)

        # Assert
        self.assertEqual(
            (shown.width, shown.height, len(shown.colours), shown.colours[0], shown.colours[-1]),
            (160, 144, 23040, 24 * 256 + 48, 167 * 256 + 207),
        )


unittest.main()
