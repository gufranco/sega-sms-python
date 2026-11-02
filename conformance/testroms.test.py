import contextlib
import hashlib
import io
import json
import os
import runpy
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import testroms  # noqa: E402

LOOP = bytes([0x18, 0xFE])

NAME_TABLE_AT_3800 = bytes([0x3E, 0xFF, 0xD3, 0xBF, 0x3E, 0x82, 0xD3, 0xBF])

WRITE_AT_3800 = bytes([0x3E, 0x00, 0xD3, 0xBF, 0x3E, 0x78, 0xD3, 0xBF])

TWO_LETTERS = bytes([0x3E, 0x28, 0xD3, 0xBE, 0x3E, 0x00, 0xD3, 0xBE, 0x3E, 0x29, 0xD3, 0xBE])

AT_3800_COUNTING_0700 = (0x3E, 0x00, 0xD3, 0xBF, 0x3E, 0x78, 0xD3, 0xBF, 0x01, 0x00, 0x07)

WRITE_ZEROS_UNTIL_DONE = (0xAF, 0xD3, 0xBE, 0x0B, 0x78, 0xB1, 0x20, 0xF8)

CLEAR_THE_NAME_TABLE = bytes((*AT_3800_COUNTING_0700, *WRITE_ZEROS_UNTIL_DONE))

SAYS_HI = NAME_TABLE_AT_3800 + CLEAR_THE_NAME_TABLE + WRITE_AT_3800 + TWO_LETTERS


def image(code: bytes) -> bytes:
    return code + LOOP + bytes(0x8000 - len(code) - len(LOOP))


def recorded(name: str) -> dict[str, Any]:
    return testroms.entry(name)


def a_record(cartridges: list[dict[str, Any]]) -> Path:
    where = Path(tempfile.mkdtemp()) / "testroms.json"
    where.write_text(json.dumps({"note": "a record", "cartridges": cartridges}))
    return where


def a_run(**fields: Any) -> dict[str, Any]:
    return {"model": "sms", "region": "usa", "script": [[2, 0xFF]], "offset": 0, **fields}


def run_main(argv: list[str], where: Path, kept: Path | None = None) -> tuple[int, str]:
    said = io.StringIO()
    with contextlib.redirect_stdout(said):
        code = testroms.main(argv, where, kept or Path(tempfile.mkdtemp()) / "none.zip")
    return code, said.getvalue()


class RecordedVerdictTest(unittest.TestCase):
    def test_the_test_suite_tells_a_japanese_console_from_an_export_one(self) -> None:
        # Arrange
        runs = recorded("test-suite-0-32")["runs"]

        # Act
        answers = {
            run["region"]: [line for line in run["verdict"] if line.startswith("JPN?")]
            for run in runs
        }

        # Assert
        self.assertEqual(answers, {"usa": ["JPN?:No"], "japan": ["JPN?:Yes"]})

    def test_and_finds_the_media_enable_port_on_both(self) -> None:
        # Arrange
        runs = recorded("test-suite-0-32")["runs"]

        # Act
        answers = [
            line for run in runs for line in run["verdict"] if line.startswith("MediaEnable")
        ]

        # Assert
        self.assertEqual(answers, ["MediaEnable?:Yes", "MediaEnable?:Yes"])

    def test_and_names_this_machine_s_console_vdp_and_processor(self) -> None:
        # Arrange
        runs = recorded("test-suite-0-32")["runs"]

        # Act
        answers = [
            [line for line in run["verdict"] if line.startswith(("Model:", "VDP?", "Z80 type"))]
            for run in runs
        ]

        # Assert
        identified = ["Model:Master System", "VDP?:315-5124", "Z80 type?:NMOS"]
        self.assertEqual(answers, [identified, identified])

    def test_the_paging_detector_finds_the_first_1k_fixed_and_the_rest_pageable(self) -> None:
        # Arrange
        verdict = recorded("paging-pfr-detect-2")["runs"][0]["verdict"]

        # Act
        regions = [line for line in verdict if line.startswith("0X")]

        # Assert
        expected = [
            "0X0000-0X03FF:          FIXED",
            "0X0400-0X3FFF:       PAGEABLE",
            "0X4000-0X7FFF:       PAGEABLE",
            "0X8000-0XBFFF:       PAGEABLE",
        ]
        self.assertEqual(regions, expected)

    def test_and_finds_both_pages_of_cartridge_ram_and_completes(self) -> None:
        # Arrange
        verdict = recorded("paging-pfr-detect-2")["runs"][0]["verdict"]

        # Act
        held = [line for line in verdict if line.endswith(("EXISTS", "TEST COMPLETE"))]

        # Assert
        self.assertEqual(
            held,
            [
                "BACKUP PAGE 0:         EXISTS",
                "PAGE 1:         EXISTS",
                "VER. 2.00        TEST COMPLETE",
            ],
        )


class ScreenTest(unittest.TestCase):
    def test_a_run_reads_what_the_cartridge_wrote_to_the_screen(self) -> None:
        # Arrange
        run = a_run(offset=-0x20)

        # Act
        found = testroms.ran(image(SAYS_HI), run)

        # Assert
        self.assertEqual(found["verdict"], ["HI"])

    def test_a_row_of_one_repeated_character_is_not_reported(self) -> None:
        # Arrange
        rows = ["  AAAA  ", " ", "OK 1"]

        # Act
        kept = [row for row in rows if testroms.reported(row)]

        # Assert
        self.assertEqual(kept, ["OK 1"])

    def test_the_script_holds_the_buttons_its_pad_byte_clears(self) -> None:
        # Arrange
        machine = testroms.machine_for(image(b""), a_run())

        # Act
        testroms.hold(machine, 0xEE)

        # Assert
        self.assertEqual(machine.console.read_port(0xDC), 0xEE)


class HandOverTest(unittest.TestCase):
    def test_a_master_system_run_starts_where_the_bios_hands_over(self) -> None:
        # Arrange
        plan = a_run()

        # Act
        machine = testroms.machine_for(image(b""), plan)

        # Assert
        self.assertEqual((machine.cpu.registers.sp, machine.console.read(0xC000)), (0xDFF0, 0xAB))

    def test_a_game_gear_run_starts_from_its_reset_values(self) -> None:
        # Arrange
        plan = a_run(model="gg")

        # Act
        machine = testroms.machine_for(image(b""), plan)

        # Assert
        self.assertNotEqual(
            (machine.cpu.registers.sp, machine.console.read(0xC000)), (0xDFF0, 0xAB)
        )


class ScriptTest(unittest.TestCase):
    def test_run_as_a_script_with_an_unknown_flag_it_prints_the_usage_and_exits_3(self) -> None:
        # Arrange
        script = ROOT / "conformance" / "testroms.py"

        # Act
        with (
            mock.patch.object(sys, "argv", [str(script), "--unknown"]),
            contextlib.redirect_stdout(io.StringIO()) as said,
            self.assertRaises(SystemExit) as ended,
        ):
            runpy.run_path(str(script), run_name="__main__")

        # Assert
        self.assertEqual((ended.exception.code, said.getvalue()), (3, testroms.USAGE + "\n"))


class PlacesTest(unittest.TestCase):
    def test_named_places_win_over_everything(self) -> None:
        # Arrange
        given = [Path("a.zip")]

        # Act
        found = testroms.places_from(given, Path("kept.zip"))

        # Assert
        self.assertEqual(found, given)

    def test_then_the_environment_variable(self) -> None:
        # Arrange
        os.environ[testroms.PLACES] = os.pathsep.join(["x.zip", "y"])

        # Act
        try:
            found = testroms.places_from([], Path("kept.zip"))
        finally:
            del os.environ[testroms.PLACES]

        # Assert
        self.assertEqual(found, [Path("x.zip"), Path("y")])

    def test_then_the_zip_kept_under_external(self) -> None:
        # Arrange
        kept = Path("kept.zip")

        # Act
        found = testroms.places_from([], kept)

        # Assert
        self.assertEqual(found, [kept])

    def test_images_are_found_by_digest_in_folders_zips_and_files(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        with zipfile.ZipFile(where / "set.zip", "w") as bundle:
            bundle.writestr("a.sms", b"a")
        (where / "b.sms").write_bytes(b"b")
        wanted = {hashlib.sha256(b"a").hexdigest(), hashlib.sha256(b"b").hexdigest()}

        # Act
        found = testroms.images([where, where / "missing"], wanted)

        # Assert
        self.assertEqual(sorted(found.values()), [b"a", b"b"])

    def test_an_image_whose_digest_is_not_listed_is_left_out(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp())
        (where / "a.sms").write_bytes(b"a")
        (where / "b.sms").write_bytes(b"b")
        wanted = {hashlib.sha256(b"b").hexdigest()}

        # Act
        found = testroms.images([where], wanted)

        # Assert
        self.assertEqual(list(found.values()), [b"b"])


class MainTest(unittest.TestCase):
    def test_an_unknown_flag_prints_the_usage(self) -> None:
        # Arrange
        where = a_record([])

        # Act
        code, said = run_main(["--fast"], where)

        # Assert
        self.assertEqual((code, testroms.USAGE in said), (testroms.USAGE_ERROR, True))

    def test_with_no_image_present_it_says_so_and_exits_2(self) -> None:
        # Arrange
        where = a_record([{"id": "x", "sha256": "ab" * 32, "outcome": "run", "runs": [a_run()]}])

        # Act
        code, said = run_main([], where)

        # Assert
        self.assertEqual((code, "SKIPPED none of the 1" in said), (testroms.NOTHING_TO_RUN, True))

    def test_a_run_that_matches_its_record_passes_and_one_absent_is_skipped(self) -> None:
        # Arrange
        rom = image(SAYS_HI)
        plan = a_run(offset=-0x20)
        held = [{**plan, **testroms.ran(rom, plan)}]
        where = a_record(
            [
                {
                    "id": "hi",
                    "sha256": hashlib.sha256(rom).hexdigest(),
                    "outcome": "run",
                    "runs": held,
                },
                {"id": "gone", "sha256": "cd" * 32, "outcome": "run", "runs": held},
            ]
        )
        (where.parent / "hi.sms").write_bytes(rom)

        # Act
        code, said = run_main([str(where.parent / "hi.sms")], where)

        # Assert
        self.assertEqual((code, "ran hi" in said, "SKIPPED gone" in said), (0, True, True))

    def test_a_run_that_differs_fails_and_write_records_what_it_saw(self) -> None:
        # Arrange
        rom = image(SAYS_HI)
        plan = a_run(offset=-0x20)
        held = [{**plan, **testroms.ran(rom, plan), "verdict": ["BYE"]}]
        where = a_record(
            [
                {
                    "id": "hi",
                    "sha256": hashlib.sha256(rom).hexdigest(),
                    "outcome": "run",
                    "runs": held,
                }
            ]
        )
        (where.parent / "hi.sms").write_bytes(rom)

        # Act
        code, said = run_main(["--write", str(where.parent / "hi.sms")], where)

        # Assert
        rewritten = json.loads(where.read_text())["cartridges"][0]["runs"][0]["verdict"]
        self.assertEqual((code, "DIFFERS hi" in said, rewritten), (1, True, ["HI"]))


unittest.main()
