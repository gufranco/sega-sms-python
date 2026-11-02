import contextlib
import io
import json
import runpy
import sys
import unittest
import urllib.error
from pathlib import Path
from typing import Any, override
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import links  # noqa: E402

ADDRESS = "https://example.com/a"

MANUAL = "https://segaretro.org/images/d/d6/SoftwareReferenceManualForSegaMarkIIIEU.pdf"


class Refusal(urllib.error.HTTPError):
    def __init__(self, code: int) -> None:
        super().__init__("https://example.invalid", code, "no", {}, None)  # type: ignore[arg-type]


class Closing(Refusal):
    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.shut = False

    @override
    def close(self) -> None:
        self.shut = True
        super().close()


class Answered:
    def __init__(self, status: int) -> None:
        self.status = status

    def __enter__(self) -> "Answered":
        return self

    def __exit__(self, *rest: object) -> None:
        return None


def answering(status: int = 200) -> Any:
    def opener(request: Any, timeout: int = 0) -> Answered:
        return Answered(status)

    return opener


def refusing(code: int) -> Any:
    def opener(request: Any, timeout: int = 0) -> Answered:
        raise Refusal(code)

    return opener


def refusing_each(refusals: tuple[Closing, ...]) -> Any:
    queue = iter(refusals)

    def opener(request: Any, timeout: int = 0) -> Answered:
        raise next(queue)

    return opener


def failing(trouble: type[Exception]) -> Any:
    def opener(request: Any, timeout: int = 0) -> Answered:
        raise trouble("no route")

    return opener


def head_refuses_get_answers() -> Any:
    def opener(request: Any, timeout: int = 0) -> Answered:
        if request.get_method() == "HEAD":
            raise Refusal(500)
        return Answered(206)

    return opener


def dead_among_live() -> Any:
    def opener(request: Any, timeout: int = 0) -> Answered:
        if "dead" in request.full_url:
            raise Refusal(404)
        return Answered(200)

    return opener


class ReadingTest(unittest.TestCase):
    def test_it_finds_the_addresses_in_a_line(self) -> None:
        # Arrange
        line = "see https://example.com/a and <https://example.com/b>"

        # Act
        found = links.addresses(line)

        # Assert
        self.assertEqual(found, ["https://example.com/a", "https://example.com/b"])

    def test_it_names_each_address_once(self) -> None:
        # Arrange
        line = "https://example.com/a https://example.com/a"

        # Act
        found = links.addresses(line)

        # Assert
        self.assertEqual(found, ["https://example.com/a"])

    def test_it_keeps_the_order_the_readme_uses(self) -> None:
        # Arrange
        line = "https://b.example https://a.example"

        # Act
        found = links.addresses(line)

        # Assert
        self.assertEqual(found, ["https://b.example", "https://a.example"])

    def test_it_drops_the_punctuation_a_sentence_leaves_behind(self) -> None:
        # Arrange
        line = "fetched from https://example.com/a.pdf."

        # Act
        found = links.addresses(line)

        # Assert
        self.assertEqual(found, ["https://example.com/a.pdf"])

    def test_it_does_not_follow_a_markdown_close_bracket(self) -> None:
        # Arrange
        line = "[title](https://example.com/a) and text"

        # Act
        found = links.addresses(line)

        # Assert
        self.assertEqual(found, ["https://example.com/a"])

    def test_it_leaves_badges_alone(self) -> None:
        # Arrange
        line = "![b](https://img.shields.io/x) [c](https://example.com/c)"

        # Act
        found = links.addresses(line)

        # Assert
        self.assertEqual(found, ["https://example.com/c"])

    def test_the_readme_of_this_project_names_the_manual_it_rests_on(self) -> None:
        # Arrange
        expected = MANUAL

        # Act
        found = links.addresses()

        # Assert
        self.assertIn(expected, found)

    def test_and_every_one_of_them_is_an_address(self) -> None:
        # Arrange
        scheme = "https://"

        # Act
        wrong = [one for one in links.addresses() if not one.startswith(scheme)]

        # Assert
        self.assertEqual(wrong, [])


class JudgementTest(unittest.TestCase):
    def test_an_address_that_answers_is_fine(self) -> None:
        # Arrange
        opener = answering(200)

        # Act
        found = links.probe(ADDRESS, opener)

        # Assert
        self.assertEqual((found.verdict, found.broken), ("ok", False))

    def test_a_not_found_is_a_broken_link(self) -> None:
        # Arrange
        opener = refusing(404)

        # Act
        found = links.probe(ADDRESS, opener)

        # Assert
        self.assertEqual((found.verdict, found.broken), ("gone", True))

    def test_so_is_a_gone(self) -> None:
        # Arrange
        opener = refusing(410)

        # Act
        found = links.probe(ADDRESS, opener)

        # Assert
        self.assertEqual((found.verdict, found.broken), ("gone", True))

    def test_a_door_held_shut_is_not_a_broken_link(self) -> None:
        # Arrange
        opener = refusing(403)

        # Act
        found = links.probe(ADDRESS, opener)

        # Assert
        self.assertEqual((found.verdict, found.broken), ("unreachable", False))

    def test_neither_is_a_host_having_a_bad_day(self) -> None:
        # Arrange
        opener = refusing(503)

        # Act
        found = links.probe(ADDRESS, opener)

        # Assert
        self.assertEqual((found.verdict, found.broken), ("unreachable", False))

    def test_nor_is_a_timeout(self) -> None:
        # Arrange
        opener = failing(TimeoutError)

        # Act
        found = links.probe(ADDRESS, opener)

        # Assert
        self.assertEqual((found.verdict, found.broken), ("unreachable", False))

    def test_a_host_that_refuses_the_cheap_question_is_asked_the_other_one(self) -> None:
        # Arrange
        opener = head_refuses_get_answers()

        # Act
        found = links.probe(ADDRESS, opener)

        # Assert
        self.assertEqual((found.verdict, found.detail), ("ok", "206"))

    def test_every_refusal_it_is_handed_is_closed(self) -> None:
        # Arrange
        refusals = tuple(Closing(503) for _ in range(links.ATTEMPTS * 2))

        # Act
        links.probe(ADDRESS, refusing_each(refusals))

        # Assert
        self.assertEqual([one.shut for one in refusals], [True] * len(refusals))

    def test_the_detail_says_what_the_last_refusal_was(self) -> None:
        # Arrange
        opener = refusing(503)

        # Act
        found = links.probe(ADDRESS, opener)

        # Assert
        self.assertEqual(found.detail, "GET 503")


class ReportTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.answers = [
            links.Answer("https://a.example", "ok", "200"),
            links.Answer("https://b.example", "gone", "404"),
            links.Answer("https://c.example", "unreachable", "GET 503"),
        ]

    def test_it_counts_everything_it_asked(self) -> None:
        # Arrange
        answers = self.answers

        # Act
        held = json.loads(links.report(answers))

        # Assert
        self.assertEqual(held["checked"], 3)

    def test_it_names_the_broken_ones_on_their_own(self) -> None:
        # Arrange
        answers = self.answers

        # Act
        held = json.loads(links.report(answers))

        # Assert
        self.assertEqual(held["gone"], ["https://b.example"])

    def test_it_keeps_the_ones_that_only_went_quiet_apart(self) -> None:
        # Arrange
        answers = self.answers

        # Act
        held = json.loads(links.report(answers))

        # Assert
        self.assertEqual(held["unreachable"], ["https://c.example"])

    def test_and_carries_every_answer_for_a_reader(self) -> None:
        # Arrange
        answers = self.answers

        # Act
        held = json.loads(links.report(answers))

        # Assert
        self.assertEqual(len(held["answers"]), 3)

    def test_a_survey_with_nothing_wrong_says_so_plainly(self) -> None:
        # Arrange
        answers = self.answers[:1]

        # Act
        held = json.loads(links.report(answers))

        # Assert
        self.assertEqual((held["gone"], held["unreachable"]), ([], []))


class SurveyTest(unittest.TestCase):
    def test_it_asks_every_address_it_is_given(self) -> None:
        # Arrange
        given = ["https://a.example", "https://b.example"]

        # Act
        found = links.survey(given, answering(200))

        # Assert
        self.assertEqual([one.address for one in found], given)

    def test_it_reports_a_dead_address_among_live_ones(self) -> None:
        # Arrange
        given = ["https://a.example", "https://dead.example"]

        # Act
        found = links.survey(given, dead_among_live())

        # Assert
        self.assertEqual([one.verdict for one in found], ["ok", "gone"])

    def test_it_reads_the_readme_when_given_nothing(self) -> None:
        # Arrange
        expected = len(links.addresses())

        # Act
        found = links.survey(None, answering(200))

        # Assert
        self.assertEqual(len(found), expected)


class ExitTest(unittest.TestCase):
    def run_with(self, answers: list[links.Answer]) -> tuple[int, str]:
        original, printed = links.survey, io.StringIO()
        links.survey = lambda *rest, **named: answers
        self.addCleanup(setattr, links, "survey", original)
        with contextlib.redirect_stdout(printed):
            code = links.main([])
        return code, printed.getvalue()

    def test_a_survey_with_nothing_gone_succeeds(self) -> None:
        # Arrange
        answers = [links.Answer("https://a.example", "ok", "200")]

        # Act
        code, _ = self.run_with(answers)

        # Assert
        self.assertEqual(code, 0)

    def test_a_quiet_host_does_not_fail_the_run(self) -> None:
        # Arrange
        answers = [links.Answer("https://a.example", "unreachable", "GET 503")]

        # Act
        code, _ = self.run_with(answers)

        # Assert
        self.assertEqual(code, 0)

    def test_but_a_broken_link_does(self) -> None:
        # Arrange
        answers = [links.Answer("https://a.example", "gone", "404")]

        # Act
        code, _ = self.run_with(answers)

        # Assert
        self.assertEqual(code, 1)

    def test_and_it_prints_the_survey_for_the_workflow_to_read(self) -> None:
        # Arrange
        answers = [links.Answer("https://a.example", "gone", "404")]

        # Act
        _, printed = self.run_with(answers)

        # Assert
        self.assertEqual(json.loads(printed)["gone"], ["https://a.example"])


class ScriptTest(unittest.TestCase):
    def test_run_as_a_script_with_no_network_every_address_is_unreachable_not_gone(self) -> None:
        # Arrange
        script = ROOT / "conformance" / "links.py"

        def unreachable(*_: Any, **__: Any) -> Any:
            raise urllib.error.URLError("offline")

        # Act
        with (
            mock.patch.object(sys, "argv", [str(script)]),
            mock.patch("urllib.request.urlopen", unreachable),
            contextlib.redirect_stdout(io.StringIO()) as said,
            self.assertRaises(SystemExit) as ended,
        ):
            runpy.run_path(str(script), run_name="__main__")

        # Assert
        self.assertEqual(
            (ended.exception.code, json.loads(said.getvalue())["unreachable"]),
            (0, links.addresses()),
        )


unittest.main()
