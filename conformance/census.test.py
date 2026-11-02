import contextlib
import hashlib
import io
import json
import runpy
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import census  # noqa: E402

IMAGE_SIZE = 0x8000

LOOP = bytes([0x18, 0xFE])

MODE_4 = bytes([0x3E, 0x04, 0xD3, 0xBF, 0x3E, 0x80, 0xD3, 0xBF])

BACKDROP_ENTRY_1 = bytes([0x3E, 0x01, 0xD3, 0xBF, 0x3E, 0x87, 0xD3, 0xBF])

CRAM_ADDRESS_17 = bytes([0x3E, 0x11, 0xD3, 0xBF, 0x3E, 0xC0, 0xD3, 0xBF])

DISPLAY_ON = bytes([0x3E, 0x40, 0xD3, 0xBF, 0x3E, 0x81, 0xD3, 0xBF])

BAR_THEN_LOOP = bytes([0x3E, 0x3F, 0xD3, 0xBE, 0x18, 0xFE])


def image(code: bytes) -> bytes:
    return code + bytes(IMAGE_SIZE - len(code))


BLANK = image(LOOP)

SWITCHES_OFF_ON_A_MASTER_SYSTEM = bytes([0x3E, 0xFF, 0xD3, 0x02])

RC_GRAND_PRIX_USA = "c789e7f9450c8eaa08be1bf6c39e877973216431"


def a_pin_list(rom: bytes) -> Path:
    where = Path(tempfile.mkdtemp()) / "boards.json"
    sha1 = hashlib.sha1(rom, usedforsecurity=False).hexdigest()
    where.write_text(json.dumps({"boards": [], "smsMode": [{"sha1": sha1, "software": "a"}]}))
    return where


DRAWING = image(MODE_4 + BACKDROP_ENTRY_1 + CRAM_ADDRESS_17 + DISPLAY_ON + BAR_THEN_LOOP)


def a_library(entries: dict[str, bytes]) -> Path:
    where = Path(tempfile.mkdtemp()) / "1 US - A-Z.zip"
    with zipfile.ZipFile(where, "w") as bundle:
        for name, data in entries.items():
            bundle.writestr(name, data)
    return where


class ExamineTest(unittest.TestCase):
    def test_an_image_that_loops_at_once_never_draws(self) -> None:
        # Arrange
        job = (BLANK, 3, census.CONSOLE, "sega", "usa")

        # Act
        found = census.examine(job)

        # Assert
        self.assertEqual((found["drew"], found["raised"]), (None, None))

    def test_the_chain_is_sha_256_over_each_frame_digest_in_order(self) -> None:
        # Arrange
        job = (BLANK, 2, census.CONSOLE, "sega", "usa")
        machine = census.build(job)
        digests = [machine.run_frame().digest() for _ in range(2)]
        expected = hashlib.sha256(b"".join(bytes.fromhex(one) for one in digests)).hexdigest()

        # Act
        found = census.examine(job)

        # Assert
        self.assertEqual(found["chain"], expected)

    def test_an_image_that_raises_is_reported_with_its_frame(self) -> None:
        # Arrange
        job = (BLANK, 2, census.CONSOLE, "no-such-board", "usa")

        # Act
        found = census.examine(job)

        # Assert
        self.assertEqual(
            (found["drew"], found["chain"], found["raised"].split(":")[0]),
            (None, None, "UnknownBoardError"),
        )

    def test_a_master_system_run_starts_where_the_export_bios_hands_over(self) -> None:
        # Arrange
        job = (BLANK, 1, census.CONSOLE, "sega", "usa")

        # Act
        machine = census.build(job)

        # Assert
        self.assertEqual(
            (machine.cpu.registers.sp, machine.console.read(0xC000)),
            (0xDFF0, 0xAB),
        )

    def test_a_game_gear_run_starts_from_its_reset_values(self) -> None:
        # Arrange
        job = (BLANK, 1, census.HANDHELD, "sega", "usa")

        # Act
        machine = census.build(job)

        # Assert
        self.assertNotEqual(
            (machine.cpu.registers.sp, machine.console.read(0xC000)),
            (0xDFF0, 0xAB),
        )

    def test_a_game_gear_image_runs_on_the_game_gear(self) -> None:
        # Arrange
        job = (BLANK, 1, census.HANDHELD, "sega", "usa")

        # Act
        machine = census.build(job)

        # Assert
        self.assertEqual((machine.console.model.name, machine.vdp.model), ("gg", "315-5378"))

    def test_a_pinned_image_runs_on_a_game_gear_in_master_system_mode(self) -> None:
        # Arrange
        job = (BLANK, 1, census.SMS_MODE, "sega", "usa")

        # Act
        machine = census.build(job)

        # Assert
        self.assertEqual(
            (machine.console.model.name, machine.console.handheld_mode, machine.windowed()),
            ("gg", False, False),
        )


class PinTest(unittest.TestCase):
    def test_the_board_list_names_the_cartridges_that_ground_pin_42(self) -> None:
        # Arrange
        listed = census.BOARDS

        # Act
        found = census.sms_mode(listed)

        # Assert
        self.assertIn(RC_GRAND_PRIX_USA, found)

    def test_only_a_listed_image_leaves_its_file_name_s_console(self) -> None:
        # Arrange
        pinned = frozenset({hashlib.sha1(DRAWING, usedforsecurity=False).hexdigest()})
        asked = [(DRAWING, "A (USA).sms"), (BLANK, "B (USA).sms"), (BLANK, "C (USA).gg")]

        # Act
        found = [census.console_of(rom, name, pinned) for rom, name in asked]

        # Assert
        self.assertEqual(found, [census.SMS_MODE, census.CONSOLE, census.HANDHELD])

    def test_a_listed_image_is_taken_in_master_system_mode(self) -> None:
        # Arrange
        drawing = MODE_4 + BACKDROP_ENTRY_1 + CRAM_ADDRESS_17 + DISPLAY_ON + BAR_THEN_LOOP
        rom = image(SWITCHES_OFF_ON_A_MASTER_SYSTEM + drawing)
        library = a_library({"R (USA).sms": rom})

        # Act
        taken = census.take([library], frames=3, jobs=1, listed=a_pin_list(rom))

        # Assert
        self.assertEqual(taken["properties"][census.DRAWS], 0)


class CulpritsTest(unittest.TestCase):
    def test_an_image_that_raised_is_named_with_what_it_raised(self) -> None:
        # Arrange
        images = [(True, BLANK, "Bad (USA).sms", "sega", "usa")]
        results = [{"drew": None, "chain": None, "raised": "KeyError: 7 at frame 3"}]

        # Act
        named = census.culprits(images, results)

        # Assert
        self.assertEqual(
            (named[census.RAISES_NOTHING], named[census.DRAWS]),
            (["Bad (USA).sms: KeyError: 7 at frame 3"], []),
        )


class TakeTest(unittest.TestCase):
    def test_a_retail_image_that_never_draws_breaks_the_drawing_property(self) -> None:
        # Arrange
        library = a_library({"Quiet (USA).sms": BLANK})

        # Act
        taken = census.take([library], frames=2, jobs=1)

        # Assert
        self.assertEqual(
            (taken["properties"][census.DRAWS], taken["culprits"][census.DRAWS]),
            (1, ["Quiet (USA).sms"]),
        )

    def test_a_drawing_image_counts_its_first_drawn_frame(self) -> None:
        # Arrange
        library = a_library({"Bar (USA).sms": DRAWING})

        # Act
        taken = census.take([library], frames=3, jobs=1)

        # Assert
        self.assertEqual(
            (taken["properties"][census.DRAWS], taken["drew"]),
            (0, {"0": 1}),
        )

    def test_a_beta_that_never_draws_is_observed_not_failed(self) -> None:
        # Arrange
        library = a_library({"Quiet (USA) (Beta).sms": BLANK})

        # Act
        taken = census.take([library], frames=2, jobs=1)

        # Assert
        self.assertEqual(
            (taken["properties"][census.DRAWS], taken["culprits"][census.BLANK]),
            (0, ["Quiet (USA) (Beta).sms"]),
        )

    def test_the_same_image_listed_twice_is_run_once(self) -> None:
        # Arrange
        library = a_library({"A (USA).sms": DRAWING, "B (USA).sms": DRAWING})

        # Act
        taken = census.take([library], frames=1, jobs=1)

        # Assert
        self.assertEqual((taken["listings"], taken["images"]), (2, 1))

    def test_each_image_is_kept_by_digest_with_its_first_drawn_frame_and_chain(self) -> None:
        # Arrange
        library = a_library({"Bar (USA).sms": DRAWING})
        digest = hashlib.sha256(DRAWING).hexdigest()

        # Act
        taken = census.take([library], frames=1, jobs=1)

        # Assert
        self.assertEqual(
            (sorted(taken["runs"]), taken["runs"][digest][0]),
            ([digest], 0),
        )

    def test_two_workers_give_what_one_does(self) -> None:
        # Arrange
        library = a_library({"A (USA).sms": DRAWING, "B (USA).sms": BLANK})
        alone = census.take([library], frames=1, jobs=1)

        # Act
        shared = census.take([library], frames=1, jobs=2)

        # Assert
        self.assertEqual(shared["runs"], alone["runs"])


class WalkTest(unittest.TestCase):
    def test_a_folder_yields_its_loose_images_and_its_archives_and_nothing_else(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        (where / "inner").mkdir()
        (where / "inner" / "A.sms").write_bytes(b"a")
        (where / "B.gg").write_bytes(b"b")
        (where / "notes.txt").write_bytes(b"c")
        with zipfile.ZipFile(where / "set.zip", "w") as bundle:
            bundle.writestr("folder/", b"")
            bundle.writestr("folder/C.sms", b"d")
            bundle.writestr("readme.txt", b"e")

        # Act
        found = sorted(census.images_in(where))

        # Assert
        self.assertEqual(
            found,
            [("inner", "A.sms", b"a"), ("set.zip", "C.sms", b"d"), (where.name, "B.gg", b"b")],
        )


class MainTest(unittest.TestCase):
    def test_a_frame_count_with_no_value_prints_the_usage_and_exits_2(self) -> None:
        # Arrange
        argv = ["somewhere", "--frames"]

        # Act
        with contextlib.redirect_stdout(io.StringIO()) as said:
            code = census.main(argv)

        # Assert
        self.assertEqual((code, said.getvalue()), (2, census.USAGE + "\n"))

    def test_a_path_that_is_not_there_is_named_and_a_run_over_nothing_fails(self) -> None:
        # Arrange
        missing = Path(tempfile.mkdtemp()) / "gone"
        into = Path(tempfile.mkdtemp()) / "corpus.json"

        # Act
        with contextlib.redirect_stdout(io.StringIO()) as said:
            code = census.main([str(missing), "--jobs", "1"], into)

        # Assert
        self.assertEqual(
            (code, said.getvalue().splitlines()[0], into.exists()),
            (1, f"absent: {missing}", False),
        )

    def test_run_as_a_script_with_no_path_it_prints_the_usage(self) -> None:
        # Arrange
        script = ROOT / "conformance" / "census.py"

        # Act
        with (
            mock.patch.object(sys, "argv", [str(script)]),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as ended,
        ):
            runpy.run_path(str(script), run_name="__main__")

        # Assert
        self.assertEqual(ended.exception.code, 2)

    def test_no_path_prints_the_usage_and_exits_2(self) -> None:
        # Arrange
        argv: list[str] = []

        # Act
        with contextlib.redirect_stdout(io.StringIO()) as said:
            code = census.main(argv)

        # Assert
        self.assertEqual((code, said.getvalue()), (2, census.USAGE + "\n"))

    def test_a_run_writes_the_corpus_and_exits_by_the_properties(self) -> None:
        # Arrange
        library = a_library({"Bar (USA).sms": DRAWING})
        into = Path(tempfile.mkdtemp()) / "corpus.json"

        # Act
        with contextlib.redirect_stdout(io.StringIO()):
            code = census.main([str(library), "--frames", "1", "--jobs", "1"], into)

        # Assert
        self.assertEqual((code, json.loads(into.read_text())["images"]), (0, 1))


unittest.main()
