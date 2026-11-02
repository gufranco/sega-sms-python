import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import ast  # noqa: E402
import contextlib  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402
import runpy  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402
from unittest import mock  # noqa: E402

from segasms import doctor  # noqa: E402

SOURCE = ROOT / "segasms" / "doctor.py"


def folder_with(name: str, text: str) -> Path:
    where = Path(tempfile.mkdtemp()) / name
    where.write_text(text)
    return where


class VersionTest(unittest.TestCase):
    def test_it_reads_the_version_out_of_the_file_beside_it(self) -> None:
        # Arrange
        beside = ROOT / "segasms" / "version.py"

        # Act
        found = doctor.installed_version(beside)

        # Assert
        self.assertEqual(found, doctor.VERSION)

    def test_a_file_with_no_version_in_it_reads_as_unknown(self) -> None:
        # Arrange
        path = folder_with("version.py", "RELEASE = 1\n")

        # Act
        found = doctor.installed_version(path)

        # Assert
        self.assertEqual(found, "unknown")


class ImportsTest(unittest.TestCase):
    def test_nothing_from_its_own_package_is_imported_at_the_top(self) -> None:
        # Arrange
        tree = ast.parse(SOURCE.read_text())

        # Act
        reached = [
            node.module or ""
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and (node.level or "segasms" in str(node.module))
        ]

        # Assert
        self.assertEqual(reached, [])


class ReachableTest(unittest.TestCase):
    def test_a_root_that_is_not_on_the_path_is_put_there(self) -> None:
        # Arrange
        path: list[str] = []

        # Act
        added = doctor.reachable(Path("/somewhere"), path)

        # Assert
        self.assertEqual((added, path), (True, ["/somewhere"]))

    def test_a_root_already_on_the_path_is_left_alone(self) -> None:
        # Arrange
        path = ["/somewhere"]

        # Act
        added = doctor.reachable(Path("/somewhere"), path)

        # Assert
        self.assertEqual((added, path), (False, ["/somewhere"]))


class FindingTest(unittest.TestCase):
    def test_a_failing_finding_carries_its_advice(self) -> None:
        # Arrange
        found = doctor.Finding("a name", False, "what was there", "what to do")

        # Act
        shown = found.report

        # Assert
        self.assertEqual(shown, f"{found.line}\n         what to do")

    def test_a_passing_finding_carries_no_advice(self) -> None:
        # Arrange
        found = doctor.Finding("a name", True, "what was there", "what to do")

        # Act
        shown = found.report

        # Assert
        self.assertEqual(shown, "  ok    a name: what was there")

    def test_a_finding_reads_as_what_it_is(self) -> None:
        # Arrange
        found = doctor.Finding("a name", False, "detail")

        # Act
        shown = repr(found)

        # Assert
        self.assertEqual(shown, "<Finding a name not ok>")


class PythonTest(unittest.TestCase):
    def test_the_interpreter_in_the_image_is_new_enough(self) -> None:
        # Arrange
        oldest = doctor.OLDEST_PYTHON

        # Act
        found = doctor.check_python(oldest)

        # Assert
        self.assertEqual(found.ok, True)

    def test_an_interpreter_older_than_asked_is_a_fault(self) -> None:
        # Arrange
        oldest = (99, 0)

        # Act
        found = doctor.check_python(oldest)

        # Assert
        self.assertEqual((found.ok, found.advice is not None), (False, True))


class PackageTest(unittest.TestCase):
    def test_the_package_imports_and_names_its_version(self) -> None:
        # Arrange
        name = "segasms"

        # Act
        found = doctor.check_package(name)

        # Assert
        self.assertEqual(
            (found.ok, found.detail), (True, f"segasms {doctor.VERSION} imported from {ROOT}")
        )

    def test_a_package_that_will_not_import_is_reported_by_what_it_threw(self) -> None:
        # Arrange
        name = "segasms_that_is_not_there"

        # Act
        found = doctor.check_package(name)

        # Assert
        self.assertEqual((found.ok, found.detail.split(":")[0]), (False, "ModuleNotFoundError"))


class MembersTest(unittest.TestCase):
    def test_the_three_members_import_with_their_versions(self) -> None:
        # Arrange
        members = doctor.MEMBERS

        # Act
        found = doctor.check_members(members)

        # Assert
        self.assertEqual(
            (found.ok, [one.split()[0] for one in found.detail.split(", ")]),
            (True, ["z80", "segavdp", "smsmapper"]),
        )

    def test_a_member_that_is_not_checked_out_is_named_with_the_fix(self) -> None:
        # Arrange
        members = {"z80": "zilog-z80-python", "not_a_member_here": "missing-python"}

        # Act
        found = doctor.check_members(members)

        # Assert
        self.assertEqual(
            (found.ok, found.detail, "submodule update" in str(found.advice)),
            (False, "not importable: missing-python", True),
        )


class CheckoutTest(unittest.TestCase):
    def test_the_checkout_and_its_members_are_visible(self) -> None:
        # Arrange
        root = ROOT

        # Act
        found = doctor.check_checkout(root)

        # Assert
        self.assertEqual(found.ok, True)

    def test_an_empty_mount_names_every_file_it_cannot_see(self) -> None:
        # Arrange
        root = Path(tempfile.mkdtemp())

        # Act
        found = doctor.check_checkout(root)

        # Assert
        self.assertEqual(
            (found.ok, found.detail),
            (False, f"not visible in {root}: {', '.join(doctor.VISIBLE)}"),
        )


class ClockTest(unittest.TestCase):
    def test_each_t_state_moves_the_vdp_three_ticks(self) -> None:
        # Arrange
        model = "sms"

        # Act
        found = doctor.check_clock(model)

        # Assert
        self.assertEqual((found.ok, found.detail), (True, "12 T states moved the VDP 36 ticks"))

    def test_a_ratio_other_than_the_one_asked_for_is_a_fault(self) -> None:
        # Arrange
        expected = 4

        # Act
        found = doctor.check_clock(expected=expected)

        # Assert
        self.assertEqual(found.ok, False)

    def test_a_machine_that_will_not_build_is_reported_by_what_it_threw(self) -> None:
        # Arrange
        model = "neo geo"

        # Act
        found = doctor.check_clock(model)

        # Assert
        self.assertEqual((found.ok, found.detail.split(":")[0]), (False, "UnknownModelError"))


class FrameTest(unittest.TestCase):
    def test_a_frame_holds_256_by_192_active_dots(self) -> None:
        # Arrange
        model = "sms"

        # Act
        found = doctor.check_frame(model)

        # Assert
        self.assertEqual((found.ok, found.detail), (True, "a frame held 49152 active dots"))

    def test_a_count_other_than_the_one_asked_for_is_a_fault(self) -> None:
        # Arrange
        expected = 1

        # Act
        found = doctor.check_frame(expected=expected)

        # Assert
        self.assertEqual(found.ok, False)

    def test_a_machine_that_will_not_build_is_reported_by_what_it_threw(self) -> None:
        # Arrange
        model = "neo geo"

        # Act
        found = doctor.check_frame(model)

        # Assert
        self.assertEqual((found.ok, found.detail.split(":")[0]), (False, "UnknownModelError"))


class LibraryTest(unittest.TestCase):
    def test_the_library_is_an_argument_so_nothing_can_be_set_wrongly(self) -> None:
        # Arrange
        name = "library"

        # Act
        found = doctor.check_library()

        # Assert
        self.assertEqual((found.name, found.ok), (name, True))


class ManualTest(unittest.TestCase):
    def test_an_absent_manual_is_reported_as_absent_and_not_as_a_fault(self) -> None:
        # Arrange
        nowhere = Path(tempfile.mkdtemp())

        # Act
        found = doctor.check_manual(held=nowhere)

        # Assert
        self.assertEqual((found.ok, found.detail.startswith("not here")), (True, True))

    def test_a_different_file_in_its_place_is_a_fault(self) -> None:
        # Arrange
        entry = json.loads(doctor.DOCUMENTS.read_text())["documents"][0]
        held = Path(tempfile.mkdtemp())
        (held / entry["file"]).parent.mkdir(parents=True)
        (held / entry["file"]).write_bytes(b"not the scan")

        # Act
        found = doctor.check_manual(held=held)

        # Assert
        self.assertEqual((found.ok, found.detail.endswith("is a different file")), (False, True))

    def test_a_record_that_will_not_parse_is_reported(self) -> None:
        # Arrange
        manifest = folder_with("documents.json", "{")

        # Act
        found = doctor.check_manual(manifest=manifest)

        # Assert
        self.assertEqual((found.ok, found.detail.startswith("JSONDecodeError")), (False, True))


class CorpusTest(unittest.TestCase):
    def test_the_corpus_here_names_the_images_behind_it(self) -> None:
        # Arrange
        held = json.loads(doctor.CORPUS.read_text())

        # Act
        found = doctor.check_corpus()

        # Assert
        self.assertEqual((found.ok, found.detail), (True, f"{held['images']} images behind it"))

    def test_an_absent_corpus_is_a_fault(self) -> None:
        # Arrange
        where = Path(tempfile.mkdtemp()) / "corpus.json"

        # Act
        found = doctor.check_corpus(where)

        # Assert
        self.assertEqual((found.ok, found.detail.startswith("not here")), (False, True))

    def test_a_corpus_over_nothing_is_a_fault(self) -> None:
        # Arrange
        where = folder_with("corpus.json", '{"images": 0}')

        # Act
        found = doctor.check_corpus(where)

        # Assert
        self.assertFalse(found.ok)

    def test_a_corpus_that_will_not_parse_is_reported(self) -> None:
        # Arrange
        where = folder_with("corpus.json", "[]")

        # Act
        found = doctor.check_corpus(where)

        # Assert
        self.assertEqual((found.ok, found.detail.startswith("TypeError")), (False, True))


class ReportTest(unittest.TestCase):
    def test_a_clean_run_says_so_and_returns_zero(self) -> None:
        # Arrange
        said: list[str] = []
        examine = lambda: [doctor.Finding("a", True, "fine")]  # noqa: E731

        # Act
        code = doctor.main((), examine, said.append)

        # Assert
        self.assertEqual((code, said[-1]), (0, "  1 checks, nothing to report"))

    def test_a_run_with_a_fault_counts_it_and_returns_one(self) -> None:
        # Arrange
        said: list[str] = []
        examine = [doctor.Finding("a", True, "fine"), doctor.Finding("b", False, "no")].copy

        # Act
        code = doctor.main((), examine, said.append)

        # Assert
        self.assertEqual((code, said[-1]), (1, "  1 of 2 checks did not pass"))

    def test_the_full_examination_covers_every_check_it_names(self) -> None:
        # Arrange
        named = list(doctor.CHECKS)

        # Act
        found = [one.name for one in doctor.examine()]

        # Assert
        self.assertEqual(found, named)


class AsDocumentedTest(unittest.TestCase):
    def test_running_it_as_a_file_prints_a_report_rather_than_a_traceback(self) -> None:
        # Arrange
        elsewhere = tempfile.mkdtemp()

        # Act
        finished = subprocess.run(
            [sys.executable, str(SOURCE)],
            capture_output=True,
            text=True,
            cwd=elsewhere,
            check=False,
        )

        # Assert
        self.assertEqual(
            ("Traceback" in finished.stderr, finished.stdout.startswith("segasms ")),
            (False, True),
        )

    def test_run_as_a_script_it_exits_by_what_it_found(self) -> None:
        # Arrange
        verdict = 0 if all(one.ok for one in doctor.examine()) else 1

        # Act
        with (
            mock.patch.object(sys, "argv", [str(SOURCE)]),
            contextlib.redirect_stdout(io.TextIOWrapper(io.BytesIO(), encoding="utf-8")),
            self.assertRaises(SystemExit) as ended,
        ):
            runpy.run_path(str(SOURCE), run_name="__main__")

        # Assert
        self.assertEqual(ended.exception.code, verdict)

    def test_the_readme_names_the_invocation_that_works(self) -> None:
        # Arrange
        readme = ROOT / "README.md"

        # Act
        said = readme.read_text()

        # Assert
        self.assertIn("scripts/run python segasms/doctor.py", said)


unittest.main()
