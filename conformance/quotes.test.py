import contextlib
import io
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import quotes  # noqa: E402


def run_main(
    text: str, sources: Path | None = None, records: Path = quotes.RECORDS
) -> tuple[int, str]:
    said = io.StringIO()
    with contextlib.redirect_stdout(said):
        code = quotes.main(text, Path(tempfile.mkdtemp()) if sources is None else sources, records)
    return code, said.getvalue()


def a_checkout_holding(files: dict[str, str]) -> Path:
    where = Path(tempfile.mkdtemp())
    for name, body in files.items():
        (where / name).parent.mkdir(parents=True, exist_ok=True)
        (where / name).write_text(body)
    return where


class CollectedTest(unittest.TestCase):
    def test_a_single_quote_is_collected_with_where_it_sits(self) -> None:
        # Arrange
        record = {"facts": {"revision": {"quote": "A software revision number byte."}}}

        # Act
        found = quotes.passages(record, "hardware.json")

        # Assert
        self.assertEqual(
            found, [("hardware.json.facts.revision", "A software revision number byte.")]
        )

    def test_a_numbered_set_is_collected_one_by_one(self) -> None:
        # Arrange
        record = {"sizeCodes": {"quotes": ["$4C 32K", "$4D 48K"]}}

        # Act
        found = quotes.passages(record, "hardware.json")

        # Assert
        self.assertEqual(
            found,
            [("hardware.json.sizeCodes[0]", "$4C 32K"), ("hardware.json.sizeCodes[1]", "$4D 48K")],
        )

    def test_a_quote_inside_a_list_is_found(self) -> None:
        # Arrange
        record = {"divergences": [{"documentSays": {"quote": "$40 256K (2M)"}}]}

        # Act
        found = quotes.passages(record, "divergences.json")

        # Assert
        self.assertEqual(found, [("divergences.json.divergences[0].documentSays", "$40 256K (2M)")])

    def test_every_record_this_member_keeps_is_read(self) -> None:
        # Arrange
        expected = set(quotes.KEPT)

        # Act
        found = {where.split(".json")[0] + ".json" for where, _ in quotes.collected()}

        # Assert
        self.assertEqual(found, expected)


class VerifyTest(unittest.TestCase):
    def test_a_quote_laid_out_across_spaces_is_still_found(self) -> None:
        # Arrange
        held = [("here", "$4A 8K (header at $1FF0)")]

        # Act
        absent = quotes.absent(held, "$4A         8K      (header at $1FF0)")

        # Assert
        self.assertEqual(absent, [])

    def test_a_quote_the_document_does_not_hold_is_named(self) -> None:
        # Arrange
        held = [("here", "A software revision number word.")]

        # Act
        absent = quotes.absent(held, "A software revision number byte.")

        # Assert
        self.assertEqual(absent, [("here", "A software revision number word.")])


class MainTest(unittest.TestCase):
    def test_without_the_manual_nothing_is_checked_and_the_run_says_so(self) -> None:
        # Arrange
        text = ""

        # Act
        code, said = run_main(text)

        # Assert
        self.assertEqual((code, "none was checked" in said), (0, True))

    def test_a_manual_holding_every_quote_passes(self) -> None:
        # Arrange
        text = " ".join(quote for _, quote in quotes.collected())

        # Act
        code, said = run_main(text)

        # Assert
        self.assertEqual((code, "0 not" in said), (0, True))

    def test_a_manual_missing_one_fails_and_names_it(self) -> None:
        # Arrange
        held = quotes.collected()
        text = " ".join(quote for _, quote in held[1:])

        # Act
        code, said = run_main(text)

        # Assert
        self.assertEqual((code, held[0][0] in said), (1, True))


class SourceCodeTest(unittest.TestCase):
    def test_a_quote_naming_a_file_is_collected_with_the_file(self) -> None:
        # Arrange
        record = {"divergences": [{"referenceSays": {"quote": "x = 1;", "file": "repo/a.c"}}]}

        # Act
        found = quotes.citations(record, "divergences.json")

        # Assert
        self.assertEqual(
            found, [("divergences.json.divergences[0].referenceSays", "x = 1;", "repo/a.c")]
        )

    def test_and_is_left_out_of_what_the_manual_must_hold(self) -> None:
        # Arrange
        record = {"divergences": [{"referenceSays": {"quote": "x = 1;", "file": "repo/a.c"}}]}

        # Act
        found = quotes.passages(record, "divergences.json")

        # Assert
        self.assertEqual(found, [])

    def test_a_source_quote_is_located_in_its_pinned_file(self) -> None:
        # Arrange
        root = a_checkout_holding({"repo/a.c": "int x;\n  x  =  1 ;\n"})

        # Act
        found = quotes.check_sources([("here", "x = 1;", "repo/a.c")], root)

        # Assert
        self.assertEqual(found, (1, []))

    def test_a_source_quote_its_file_does_not_hold_is_named(self) -> None:
        # Arrange
        root = a_checkout_holding({"repo/a.c": "x = 2;"})

        # Act
        found = quotes.check_sources([("here", "x = 1;", "repo/a.c")], root)

        # Assert
        self.assertEqual(found, (1, [("here", "x = 1;")]))

    def test_a_source_quote_whose_checkout_is_absent_is_counted_unchecked(self) -> None:
        # Arrange
        root = Path(tempfile.mkdtemp())

        # Act
        found = quotes.check_sources([("here", "x = 1;", "repo/a.c")], root)

        # Assert
        self.assertEqual(found, (0, []))

    def test_every_source_quote_the_records_carry_is_counted_in_the_run(self) -> None:
        # Arrange
        text = " ".join(quote for _, quote in quotes.collected())

        # Act
        _, said = run_main(text)

        # Assert
        self.assertIn(f"{len(quotes.cited())} quotes from source code, 0 checked", said)

    def test_a_checkout_missing_a_quote_fails_the_run(self) -> None:
        # Arrange
        record = {"notStated": {"x": {"quote": "x = 1;", "file": "repo/a.c"}}}
        records = a_checkout_holding({"hardware.json": json.dumps(record)})
        root = a_checkout_holding({"repo/a.c": "nothing here"})

        # Act
        code, said = run_main("", root, records)

        # Assert
        self.assertEqual((code, "hardware.json.notStated.x: x = 1;" in said), (1, True))


class ScriptTest(unittest.TestCase):
    def test_run_as_a_script_it_reports_and_exits_0(self) -> None:
        # Arrange
        script = ROOT / "conformance" / "quotes.py"

        # Act
        with (
            mock.patch.object(sys, "argv", [str(script)]),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as ended,
        ):
            runpy.run_path(str(script), run_name="__main__")

        # Assert
        self.assertEqual(ended.exception.code, 0)


unittest.main()
