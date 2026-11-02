import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import contextlib  # noqa: E402
import io  # noqa: E402
import runpy  # noqa: E402
import subprocess  # noqa: E402
import tempfile  # noqa: E402
import unittest  # noqa: E402
from unittest import mock  # noqa: E402

from conformance import source  # noqa: E402


def written(text: str) -> Path:
    path = Path(tempfile.mkdtemp()) / "sample.py"
    path.write_text(text)
    return path


class StringsTest(unittest.TestCase):
    def test_a_module_string_is_found(self) -> None:
        # Arrange
        path = written('"""Module."""\n\nVALUE = 1\n')

        # Act
        found = source.strings_in(path)

        # Assert
        self.assertEqual(found, [1])

    def test_a_class_and_a_function_string_are_found(self) -> None:
        # Arrange
        path = written('class A:\n    """Class."""\n\n\ndef f() -> None:\n    """Function."""\n')

        # Act
        found = source.strings_in(path)

        # Assert
        self.assertEqual(found, [2, 6])

    def test_a_string_after_an_assignment_is_found(self) -> None:
        # Arrange
        path = written('LIMIT = 3\n"""What the limit is."""\n')

        # Act
        found = source.strings_in(path)

        # Assert
        self.assertEqual(found, [2])

    def test_a_string_used_as_a_value_is_not_one(self) -> None:
        # Arrange
        path = written('NAME = "a value"\nprint("a call")\n')

        # Act
        found = source.strings_in(path)

        # Assert
        self.assertEqual(found, [])


class RepositoryTest(unittest.TestCase):
    def test_no_tracked_file_carries_a_documentation_string(self) -> None:
        # Arrange
        root = ROOT

        # Act
        found = source.offenders(root)

        # Assert
        self.assertEqual(found, [])

    def test_and_there_are_files_to_check(self) -> None:
        # Arrange
        root = ROOT

        # Act
        files = source.tracked_python(root)

        # Assert
        self.assertGreater(len(files), 10)


class MainTest(unittest.TestCase):
    def test_a_clean_tree_reports_what_it_examined(self) -> None:
        # Arrange
        said = io.StringIO()

        # Act
        with contextlib.redirect_stdout(said):
            code = source.main([])

        # Assert
        self.assertEqual(code, 0)
        self.assertIn("files examined, none carries a documentation string", said.getvalue())

    def test_a_tree_with_one_names_it_and_fails(self) -> None:
        # Arrange
        said = io.StringIO()
        path = written('"""Module."""\n')

        # Act
        with contextlib.redirect_stdout(said):
            code = source.report([(path, [1])], 1)

        # Assert
        self.assertEqual(code, 1)
        self.assertIn(f"{path}:1", said.getvalue())


class ScriptTest(unittest.TestCase):
    def test_run_as_a_script_on_a_repository_with_no_python_it_examines_none(self) -> None:
        # Arrange
        script = ROOT / "conformance" / "source.py"
        where = tempfile.mkdtemp()
        subprocess.run(["git", "init", "--quiet", where], check=True)

        # Act
        with (
            mock.patch.object(sys, "argv", [str(script), where]),
            contextlib.redirect_stdout(io.StringIO()) as said,
            self.assertRaises(SystemExit) as ended,
        ):
            runpy.run_path(str(script), run_name="__main__")

        # Assert
        self.assertEqual(
            (ended.exception.code, said.getvalue()),
            (0, "0 files examined, none carries a documentation string\n"),
        )


unittest.main()
