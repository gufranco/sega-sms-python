import contextlib
import io
import runpy
import struct
import sys
import tempfile
import unittest
import wave
import zlib
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from segasms import record  # noqa: E402

MODE_4 = (0x3E, 0x04, 0xD3, 0xBF, 0x3E, 0x80, 0xD3, 0xBF)

BACKDROP_IS_ENTRY_1 = (0x3E, 0x01, 0xD3, 0xBF, 0x3E, 0x87, 0xD3, 0xBF)

ADDRESS_CRAM_17 = (0x3E, 0x11, 0xD3, 0xBF, 0x3E, 0xC0, 0xD3, 0xBF)

WRITE_3F_AND_LOOP = (0x3E, 0x3F, 0xD3, 0xBE, 0x18, 0xFE)

WHITE = bytes((*MODE_4, *BACKDROP_IS_ENTRY_1, *ADDRESS_CRAM_17, *WRITE_3F_AND_LOOP))

PROCESSOR_HZ = 3_580_000

Chunk = tuple[bytes, bytes, bool]


def kept(name: str) -> Path:
    where = Path(tempfile.mkdtemp()) / name
    where.write_bytes(WHITE + bytes(0x8000 - len(WHITE)))
    return where


def chunks(png: bytes) -> list[Chunk]:
    found = []
    at = 8
    while at < len(png):
        (length,) = struct.unpack_from(">I", png, at)
        kind = png[at + 4 : at + 8]
        data = png[at + 8 : at + 8 + length]
        (crc,) = struct.unpack_from(">I", png, at + 8 + length)
        found.append((kind, data, crc == zlib.crc32(kind + data)))
        at += 12 + length
    return found


def recorded(name: str, frames: int) -> tuple[int, str, Path]:
    out = Path(tempfile.mkdtemp())
    with contextlib.redirect_stdout(io.StringIO()) as said:
        code = record.main([str(kept(name)), "--frames", str(frames), "--out", str(out)])
    return code, said.getvalue(), out


def run_main(argv: list[str]) -> tuple[int, str]:
    with contextlib.redirect_stdout(io.StringIO()) as said:
        code = record.main(argv)
    return code, said.getvalue()


class ColourTest(unittest.TestCase):
    def test_console_words_spread_two_bits_a_channel_over_a_byte(self) -> None:
        # Arrange
        words = (0x3F, 0x03, 0x0C, 0x30, 0x15)

        # Act
        found = [record.rgb(word, handheld=False) for word in words]

        # Assert
        self.assertEqual(
            found,
            [
                b"\xff\xff\xff",
                b"\xff\x00\x00",
                b"\x00\xff\x00",
                b"\x00\x00\xff",
                b"\x55\x55\x55",
            ],
        )

    def test_game_gear_words_spread_four_bits_a_channel_over_a_byte(self) -> None:
        # Arrange
        words = (0x0FFF, 0x000F, 0x00F0, 0x0F00, 0x0888)

        # Act
        found = [record.rgb(word, handheld=True) for word in words]

        # Assert
        self.assertEqual(
            found,
            [
                b"\xff\xff\xff",
                b"\xff\x00\x00",
                b"\x00\xff\x00",
                b"\x00\x00\xff",
                b"\x88\x88\x88",
            ],
        )


class DelayTest(unittest.TestCase):
    def test_a_frame_lasts_its_t_states_over_the_processor_clock(self) -> None:
        # Arrange
        states = 59736

        # Act
        numerator, denominator = record.delay(states)

        # Assert
        self.assertEqual(
            (denominator <= 0xFFFF, round(numerator / denominator, 9)),
            (True, round(states / PROCESSOR_HZ, 9)),
        )


class AnimationTest(unittest.TestCase):
    def test_the_animation_is_a_png_with_one_control_chunk_a_frame(self) -> None:
        # Arrange
        code, _, out = recorded("white.sms", 3)

        # Act
        found = chunks((out / "white.png").read_bytes())

        # Assert
        self.assertEqual(
            (code, [kind for kind, _, _ in found], all(good for _, _, good in found)),
            (
                0,
                [b"IHDR", b"acTL", b"fcTL", b"IDAT", b"fcTL", b"fdAT", b"fcTL", b"fdAT", b"IEND"],
                True,
            ),
        )

    def test_a_master_system_picture_is_256_by_192_and_its_backdrop_is_white(self) -> None:
        # Arrange
        _, _, out = recorded("white.sms", 2)

        # Act
        found = chunks((out / "white.png").read_bytes())

        # Assert
        header, last = found[0][1], zlib.decompress(found[-2][1][4:])
        self.assertEqual(
            (struct.unpack_from(">II", header), last[:4], len(last)),
            ((256, 192), b"\x00\xff\xff\xff", 192 * (1 + 256 * 3)),
        )

    def test_a_game_gear_in_master_system_mode_records_the_whole_picture(self) -> None:
        # Arrange
        out = Path(tempfile.mkdtemp())
        argv = [str(kept("white.sms")), "--frames", "1", "--mode", "master-system", "--out"]

        # Act
        code, _ = run_main([*argv, str(out)])

        # Assert
        found = chunks((out / "white.png").read_bytes())
        self.assertEqual((code, struct.unpack_from(">II", found[0][1])), (0, (256, 192)))

    def test_a_game_gear_picture_is_its_160_by_144_window(self) -> None:
        # Arrange
        _, _, out = recorded("white.gg", 1)

        # Act
        found = chunks((out / "white.png").read_bytes())

        # Assert
        self.assertEqual(struct.unpack_from(">II", found[0][1]), (160, 144))


class SoundTest(unittest.TestCase):
    def test_the_sound_is_16_bit_stereo_at_44100_hertz_as_long_as_the_frames(self) -> None:
        # Arrange
        _, _, out = recorded("white.sms", 2)
        delays = [
            struct.unpack_from(">HH", data, 20)
            for kind, data, _ in chunks((out / "white.png").read_bytes())
            if kind == b"fcTL"
        ]
        seconds = sum(numerator / denominator for numerator, denominator in delays)

        # Act
        with wave.open(str(out / "white.wav")) as sound:
            found = (sound.getnchannels(), sound.getsampwidth(), sound.getframerate())
            length = sound.getnframes()

        # Assert
        self.assertEqual((found, abs(length - seconds * 44100) <= 2), ((2, 2, 44100), True))


class MainTest(unittest.TestCase):
    def test_a_recording_names_both_files_it_wrote(self) -> None:
        # Arrange
        frames = 1

        # Act
        code, said, out = recorded("white.sms", frames)

        # Assert
        self.assertEqual(
            (code, [line.split(":")[0] for line in said.splitlines()]),
            (0, [str(out / "white.png"), str(out / "white.wav")]),
        )

    def test_no_image_prints_the_usage_and_exits_2(self) -> None:
        # Arrange
        argv: list[str] = []

        # Act
        found = run_main(argv)

        # Assert
        self.assertEqual(found, (2, record.USAGE + "\n"))

    def test_an_image_of_another_console_prints_the_usage(self) -> None:
        # Arrange
        argv = ["game.sg"]

        # Act
        found = run_main(argv)

        # Assert
        self.assertEqual(found, (2, record.USAGE + "\n"))

    def test_a_mode_other_than_own_or_master_system_prints_the_usage(self) -> None:
        # Arrange
        argv = ["game.gg", "--mode", "sg-1000"]

        # Act
        found = run_main(argv)

        # Assert
        self.assertEqual(found, (2, record.USAGE + "\n"))

    def test_a_board_smsmapper_does_not_have_prints_the_usage(self) -> None:
        # Arrange
        argv = ["game.sms", "--board", "nothing"]

        # Act
        found = run_main(argv)

        # Assert
        self.assertEqual(found, (2, record.USAGE + "\n"))

    def test_a_frame_count_that_is_not_a_positive_number_prints_the_usage(self) -> None:
        # Arrange
        attempts = (["game.sms", "--frames", "0"], ["game.sms", "--frames", "many"])

        # Act
        found = {run_main(argv) for argv in attempts}

        # Assert
        self.assertEqual(found, {(2, record.USAGE + "\n")})

    def test_two_images_print_the_usage(self) -> None:
        # Arrange
        argv = ["one.sms", "two.sms"]

        # Act
        found = run_main(argv)

        # Assert
        self.assertEqual(found, (2, record.USAGE + "\n"))

    def test_an_image_that_is_not_there_is_named(self) -> None:
        # Arrange
        missing = Path(tempfile.mkdtemp()) / "gone.sms"

        # Act
        found = run_main([str(missing)])

        # Assert
        self.assertEqual(found, (2, f"record: cannot read {missing}.\n"))


class StartTest(unittest.TestCase):
    def test_without_a_bios_a_master_system_starts_where_the_bios_hands_over(self) -> None:
        # Arrange
        image = WHITE + bytes(0x8000 - len(WHITE))

        # Act
        machine = record.start(image, "sms", "sega")

        # Assert
        self.assertEqual(
            (machine.cpu.registers.pc, machine.cpu.registers.sp, machine.console.read(0xC000)),
            (0x0000, 0xDFF0, 0xAB),
        )

    def test_with_a_bios_the_machine_starts_in_the_bios(self) -> None:
        # Arrange
        image = bytes(0x8000)
        bios = WHITE + bytes(0x2000 - len(WHITE))

        # Act
        machine = record.start(image, "sms", "sega", bios)
        drawn = [machine.run_frame() for _ in range(2)][-1]

        # Assert
        self.assertEqual(set(drawn.colours), {0x3F})

    def test_a_bios_that_is_not_there_is_named(self) -> None:
        # Arrange
        missing = Path(tempfile.mkdtemp()) / "bios.sms"

        # Act
        found = run_main([str(kept("white.sms")), "--bios", str(missing)])

        # Assert
        self.assertEqual(found, (2, f"record: cannot read {missing}.\n"))


class ScriptTest(unittest.TestCase):
    def test_run_as_a_script_with_no_image_it_prints_the_usage(self) -> None:
        # Arrange
        script = ROOT / "segasms" / "record.py"

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
