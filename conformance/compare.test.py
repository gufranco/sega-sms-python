import contextlib
import io
import runpy
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import census, compare  # noqa: E402

MODE_4 = (0x3E, 0x04, 0xD3, 0xBF, 0x3E, 0x80, 0xD3, 0xBF)

BACKDROP_IS_ENTRY_1 = (0x3E, 0x01, 0xD3, 0xBF, 0x3E, 0x87, 0xD3, 0xBF)

ADDRESS_CRAM_17 = (0x3E, 0x11, 0xD3, 0xBF, 0x3E, 0xC0, 0xD3, 0xBF)

WRITE_3F_AND_LOOP = (0x3E, 0x3F, 0xD3, 0xBE, 0x18, 0xFE)

WHITE = bytes((*MODE_4, *BACKDROP_IS_ENTRY_1, *ADDRESS_CRAM_17, *WRITE_3F_AND_LOOP))


def image(code: bytes) -> bytes:
    return code + bytes(0x8000 - len(code))


def shifted(*_: object) -> list[tuple[int, ...]]:
    return [(0,)] * 10


def kept(name: str, data: bytes) -> Path:
    where = Path(tempfile.mkdtemp()) / name
    where.write_bytes(data)
    return where


class PixelTest(unittest.TestCase):
    def test_console_white_and_black_map_to_rgb565_white_and_black(self) -> None:
        # Arrange
        words = (0x3F, 0x00, 0x03)

        # Act
        found = [compare.pixel(word, handheld=False) for word in words]

        # Assert
        self.assertEqual(found, [0xFFFF, 0x0000, 0xF800])

    def test_a_game_gear_word_keeps_its_four_bits_a_channel(self) -> None:
        # Arrange
        words = (0x0FFF, 0x000F, 0x0F00)

        # Act
        found = [compare.pixel(word, handheld=True) for word in words]

        # Assert
        self.assertEqual(found, [0xFFFF, 0xF800, 0x001F])


class FramesTest(unittest.TestCase):
    def test_this_machine_frames_a_game_gear_to_its_window(self) -> None:
        # Arrange
        rom = image(WHITE)

        # Act
        found = compare.ours(rom, census.HANDHELD, 1)

        # Assert
        self.assertEqual(len(found[0]), 160 * 144)

    def test_a_game_gear_in_master_system_mode_is_compared_whole(self) -> None:
        # Arrange
        rom = image(WHITE)

        # Act
        found = compare.ours(rom, census.SMS_MODE, 1)

        # Assert
        self.assertEqual(len(found[0]), 256 * 192)

    def test_genesis_plus_gx_gives_every_frame_it_was_asked_for(self) -> None:
        # Arrange
        rom = image(WHITE)

        # Act
        found = compare.theirs(rom, ".sms", 3)

        # Assert
        self.assertEqual([len(one) for one in found], [256 * 192] * 3)


class AlignmentTest(unittest.TestCase):
    def test_frames_that_agree_one_frame_apart_align_with_that_offset(self) -> None:
        # Arrange
        ours, theirs = [(0,), (1,), (2,), (3,)], [(9,), (8,), (1,), (2,), (3,)]

        # Act
        found = compare.aligned(ours, theirs, skipped=1)

        # Assert
        self.assertEqual(found, (1, None, 0))

    def test_frames_that_agree_in_step_keep_no_offset(self) -> None:
        # Arrange
        ours, theirs = [(0,), (1,), (2,), (3,)], [(5,), (1,), (2,), (3,)]

        # Act
        found = compare.aligned(ours, theirs, skipped=1)

        # Assert
        self.assertEqual(found, (0, None, 0))

    def test_the_offset_with_fewest_differing_frames_wins_and_names_the_first(self) -> None:
        # Arrange
        ours = [(0,), (1,), (2,), (3,), (4,), (5,)]
        theirs = [(0,), (1,), (9,), (2,), (9,), (4,), (5,)]

        # Act
        found = compare.aligned(ours, theirs, skipped=1)

        # Assert
        self.assertEqual(found, (1, 3, 1))

    def test_frames_that_differ_at_every_offset_keep_no_offset_on_a_tie(self) -> None:
        # Arrange
        ours, theirs = [(0,), (1,), (7,), (8,)], [(0,), (1,), (8,), (9,)]

        # Act
        found = compare.aligned(ours, theirs, skipped=1)

        # Assert
        self.assertEqual(found, (0, 2, 1))


class MainTest(unittest.TestCase):
    def test_an_image_both_machines_draw_alike_passes(self) -> None:
        # Arrange
        rom = kept("white.sms", image(WHITE))

        # Act
        with contextlib.redirect_stdout(io.StringIO()) as said:
            code = compare.main([str(rom), "--frames", "8"])

        # Assert
        self.assertEqual(
            (code, said.getvalue()),
            (0, "same white.sms: 8 frames, in step\n1 images, 1 the same, 0 differ\n"),
        )

    def test_an_archive_is_walked_and_each_distinct_image_compared_once(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp()) / "set.zip"
        with zipfile.ZipFile(where, "w") as bundle:
            bundle.writestr("a.sms", image(WHITE))
            bundle.writestr("b.sms", image(WHITE))

        # Act
        with contextlib.redirect_stdout(io.StringIO()) as said:
            code = compare.main([str(where), "--frames", "8"])

        # Assert
        self.assertEqual(
            (code, said.getvalue().splitlines()[-1]), (0, "1 images, 1 the same, 0 differ")
        )

    def test_a_run_with_no_image_prints_the_usage_and_exits_2(self) -> None:
        # Arrange
        argv = ["--frames", "4"]

        # Act
        with contextlib.redirect_stdout(io.StringIO()) as said:
            code = compare.main(argv)

        # Assert
        self.assertEqual((code, said.getvalue()), (2, compare.USAGE + "\n"))

    def test_a_flag_left_without_its_value_names_no_image(self) -> None:
        # Arrange
        argv = ["--frames"]

        # Act
        with contextlib.redirect_stdout(io.StringIO()) as said:
            code = compare.main(argv)

        # Assert
        self.assertEqual((code, said.getvalue()), (2, compare.USAGE + "\n"))

    def test_an_image_that_differs_is_named_with_its_frame_and_fails(self) -> None:
        # Arrange
        rom = kept("white.sms", image(WHITE))

        # Act
        with contextlib.redirect_stdout(io.StringIO()) as said:
            code = compare.main([str(rom), "--frames", "10"], ours=shifted)

        # Assert
        self.assertEqual(
            (code, said.getvalue()),
            (
                1,
                "DIFFERS white.sms: 3 frames from frame 6, in step\n1 images, 0 the same, 1 differ\n",
            ),
        )


class ScriptTest(unittest.TestCase):
    def test_run_as_a_script_with_no_image_it_prints_the_usage(self) -> None:
        # Arrange
        script = ROOT / "conformance" / "compare.py"

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
