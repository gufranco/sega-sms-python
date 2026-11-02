from __future__ import annotations

import contextlib
import importlib
import re
import subprocess
import sys
import unittest
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parent.parent

README = ROOT / "README.md"


def packages() -> list[str]:
    return sorted(
        found.name
        for found in ROOT.iterdir()
        if (found / "__init__.py").is_file() and found.name != "conformance"
    )


def cannot_run_here(named: list[str] | None = None) -> str | None:
    for name in packages() if named is None else named:
        asked = getattr(importlib.import_module(name), "why_not", None)
        if callable(asked):
            answer = asked()
            return str(answer) if answer else None
    return None


def excused(failure: str, reason: str | None = None) -> bool:
    said = cannot_run_here() if reason is None else reason
    return bool(said) and str(said)[:40] in failure


BLOCK = re.compile(r"^```(\w*)\n(.*?)^```$", re.M | re.S)


def blocks(text: str | None = None) -> list[tuple[str, str]]:
    return [
        (lang, body)
        for lang, body in BLOCK.findall(text if text is not None else README.read_text())
    ]


def examples(text: str | None = None) -> list[tuple[str, str | None]]:
    found = blocks(text)
    paired: list[tuple[str, str | None]] = []
    for index, (lang, body) in enumerate(found):
        if lang != "python":
            continue
        after = found[index + 1] if index + 1 < len(found) else None
        paired.append((body, after[1] if after and after[0] == "" else None))
    return paired


def ran(source: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", source],
        capture_output=True,
        check=False,
        text=True,
        cwd=ROOT,
        timeout=120,
    )


def broken(found: list[tuple[str, str | None]], reason: str | None = None) -> list[str]:
    failed = []
    reason = cannot_run_here() if reason is None else reason
    for source, _ in found:
        finished = ran(source)
        if finished.returncode == 0:
            continue
        if excused(finished.stderr, reason):
            continue
        said = finished.stderr.strip().splitlines()
        failed.append(said[-1] if said else f"exited {finished.returncode} in silence")
    return failed


def mismatched(
    found: list[tuple[str, str | None]], reason: str | None = None
) -> list[tuple[str, str]]:
    wrong = []
    reason = cannot_run_here() if reason is None else reason
    for source, expected in found:
        if expected is None:
            continue
        finished = ran(source)
        if finished.returncode != 0 and excused(finished.stderr, reason):
            continue
        if finished.stdout != expected:
            wrong.append((expected.strip(), finished.stdout.strip()))
    return wrong


@contextlib.contextmanager
def installed(name: str, module: ModuleType) -> Iterator[None]:
    sys.modules[name] = module
    try:
        yield
    finally:
        del sys.modules[name]


def publishing(name: str, answer: str | None) -> ModuleType:
    module = ModuleType(name)
    module.why_not = lambda: answer  # type: ignore[attr-defined]
    return module


FIRMWARE = "no firmware image was found: this backend runs the part's own microcode"


class WorkedExampleTest(unittest.TestCase):
    def test_there_are_examples_to_check(self) -> None:
        # Arrange
        readme = README.read_text()

        # Act
        found = examples(readme)

        # Assert
        self.assertGreaterEqual(len(found), 4)

    def test_every_example_that_can_run_here_runs(self) -> None:
        # Arrange
        found = examples()

        # Act
        failed = broken(found)

        # Assert
        self.assertEqual(failed, [])

    def test_every_example_prints_what_the_readme_says_it_prints(self) -> None:
        # Arrange
        found = examples()

        # Act
        wrong = mismatched(found)

        # Assert
        self.assertEqual(wrong, [])

    def test_every_example_is_run_and_none_is_skipped(self) -> None:
        # Arrange
        readme = README.read_text()

        # Act
        found = examples(readme)

        # Assert
        self.assertEqual(len([body for body, _ in found if body.strip()]), len(found))


class CheckerTest(unittest.TestCase):
    def test_an_example_that_runs_is_not_reported(self) -> None:
        # Arrange
        readme = "```python\nprint(1)\n```\n"

        # Act
        failed = broken(examples(readme))

        # Assert
        self.assertEqual(failed, [])

    def test_an_example_that_raises_is_reported(self) -> None:
        # Arrange
        readme = '```python\nraise ValueError("nope")\n```\n'

        # Act
        failed = broken(examples(readme))

        # Assert
        self.assertEqual(failed, ["ValueError: nope"])

    def test_an_example_that_fails_in_silence_is_still_reported(self) -> None:
        # Arrange
        readme = "```python\nraise SystemExit(3)\n```\n"

        # Act
        failed = broken(examples(readme))

        # Assert
        self.assertEqual(failed, ["exited 3 in silence"])

    def test_an_example_that_prints_the_wrong_thing_is_reported(self) -> None:
        # Arrange
        readme = "```python\nprint(1)\n```\n\n```\n2\n```\n"

        # Act
        wrong = mismatched(examples(readme))

        # Assert
        self.assertEqual(wrong, [("2", "1")])

    def test_and_a_later_example_is_still_checked_after_an_earlier_one_failed(self) -> None:
        # Arrange
        readme = (
            "```python\nprint(1)\n```\n\n```\n2\n```\n\n```python\nprint(3)\n```\n\n```\n3\n```\n"
        )

        # Act
        wrong = mismatched(examples(readme))

        # Assert
        self.assertEqual(wrong, [("2", "1")])

    def test_an_example_with_no_stated_output_is_only_run(self) -> None:
        # Arrange
        readme = "```python\nprint(1)\n```\n"

        # Act
        wrong = mismatched(examples(readme))

        # Assert
        self.assertEqual(wrong, [])

    def test_a_member_that_can_run_everything_excuses_nothing(self) -> None:
        # Arrange
        reason = None if cannot_run_here() else "x" * 60

        # Act
        forgiven = excused("anything at all", reason)

        # Assert
        self.assertFalse(forgiven)

    def test_a_failure_the_member_says_it_expects_is_excused(self) -> None:
        # Arrange
        failure = f"Traceback\nNoFirmware: {FIRMWARE}"

        # Act
        forgiven = excused(failure, FIRMWARE)

        # Assert
        self.assertTrue(forgiven)

    def test_and_any_other_failure_is_not(self) -> None:
        # Arrange
        failure = "Traceback\nZeroDivisionError: division by zero"

        # Act
        forgiven = excused(failure, FIRMWARE)

        # Assert
        self.assertFalse(forgiven)

    def test_and_a_member_that_publishes_no_reason_excuses_nothing(self) -> None:
        # Arrange
        failure = "Traceback\nNoFirmware: anything"

        # Act
        forgiven = excused(failure, "")

        # Assert
        self.assertFalse(forgiven)

    def test_an_example_that_only_this_machine_can_run_is_reported_as_broken(self) -> None:
        # Arrange
        readme = "```python\nraise ValueError('nope')\n```\n"

        # Act
        failed = broken(examples(readme))

        # Assert
        self.assertEqual(failed, ["ValueError: nope"])

    def test_an_example_the_member_says_it_cannot_run_is_not_reported_as_broken(self) -> None:
        # Arrange
        readme = "```python\nraise SystemExit('no image is here')\n```\n"

        # Act
        failed = broken(examples(readme), "no image is here")

        # Assert
        self.assertEqual(failed, [])

    def test_and_its_stated_output_is_not_compared_either(self) -> None:
        # Arrange
        readme = "```python\nraise SystemExit('no image is here')\n```\n\n```\n7\n```\n"

        # Act
        wrong = mismatched(examples(readme), "no image is here")

        # Assert
        self.assertEqual(wrong, [])

    def test_a_member_that_publishes_a_reason_is_read(self) -> None:
        # Arrange
        speaking = publishing("speaking", "no image is here")

        # Act
        with installed("speaking", speaking):
            said = cannot_run_here(["speaking"])

        # Assert
        self.assertEqual(said, "no image is here")

    def test_and_one_that_publishes_nothing_to_say_says_nothing(self) -> None:
        # Arrange
        quiet = publishing("quiet", None)

        # Act
        with installed("quiet", quiet):
            said = cannot_run_here(["quiet"])

        # Assert
        self.assertIsNone(said)

    def test_and_one_that_publishes_no_such_call_is_passed_over(self) -> None:
        # Arrange
        silent = ModuleType("silent")

        # Act
        with installed("silent", silent):
            said = cannot_run_here(["silent"])

        # Assert
        self.assertIsNone(said)

    def test_the_member_this_repository_holds_is_found_by_name(self) -> None:
        # Arrange
        excluded = "conformance"

        # Act
        found = packages()

        # Assert
        self.assertNotIn(excluded, found)


unittest.main(verbosity=2)
