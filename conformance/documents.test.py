import contextlib
import hashlib
import io
import json
import runpy
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, override
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import documents as _documents  # noqa: E402

documents: Any = _documents

HELD = json.loads((ROOT / "conformance" / "documents.json").read_text())

PRESENT = all((ROOT / "docs" / entry["file"]).is_file() for entry in HELD["documents"])

MANUAL = "SoftwareReferenceManualForSegaMarkIII"


def a_file(where: Path, name: str, body: bytes) -> dict[str, Any]:
    path = where / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return {
        "file": name,
        "rung": 1,
        "retrievedFrom": path.resolve().as_uri(),
        "sha256": hashlib.sha256(body).hexdigest(),
        "bytes": len(body),
    }


class BrowsersOnly(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        agent = self.headers.get("User-Agent", "")
        allowed = agent.startswith("Mozilla/")
        body = b"a document" if allowed else b"forbidden"
        self.send_response(200 if allowed else 403)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    @override
    def log_message(self, *_args: object) -> None:
        return


def a_server_that_refuses_curl(test: unittest.TestCase) -> str:
    server = ThreadingHTTPServer(("127.0.0.1", 0), BrowsersOnly)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    test.addCleanup(server.server_close)
    test.addCleanup(server.shutdown)
    return f"http://127.0.0.1:{server.server_address[1]}/held.pdf"


def stand_in(test: unittest.TestCase, entries: list[dict[str, Any]]) -> None:
    held = documents.documents
    documents.documents = lambda *_args: entries
    test.addCleanup(setattr, documents, "documents", held)


class ManifestTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.entries: list[dict[str, Any]] = HELD["documents"]

    def test_the_repository_declares_the_documents_it_was_read_from(self) -> None:
        # Arrange
        minimum = 1

        # Act
        count = len(self.entries)

        # Assert
        self.assertGreaterEqual(count, minimum)

    def test_every_document_carries_a_digest_of_the_full_width(self) -> None:
        # Arrange
        width = 64

        # Act
        short = [entry["file"] for entry in self.entries if len(entry["sha256"]) != width]

        # Assert
        self.assertEqual(short, [])

    def test_every_document_says_where_it_came_from(self) -> None:
        # Arrange
        scheme = "http"

        # Act
        missing = [
            entry["file"]
            for entry in self.entries
            if not str(entry.get("retrievedFrom", "")).startswith(scheme)
        ]

        # Assert
        self.assertEqual(missing, [])

    def test_every_document_says_which_rung_it_sits_on(self) -> None:
        # Arrange
        allowed = {1, 3, 4}

        # Act
        rungs = {entry["rung"] for entry in self.entries}

        # Assert
        self.assertLessEqual(rungs, allowed)

    def test_the_ladder_says_why_the_second_rung_is_empty_here(self) -> None:
        # Arrange
        second = HELD["authority"]["2"]

        # Act
        explained = "Nothing here" in second

        # Assert
        self.assertTrue(explained, second)

    def test_every_document_says_what_it_covers(self) -> None:
        # Arrange
        entries = self.entries

        # Act
        empty = [entry["file"] for entry in entries if not entry.get("covers")]

        # Assert
        self.assertEqual(empty, [])

    def test_a_part_with_no_document_says_what_is_known_about_it_instead(self) -> None:
        # Arrange
        shortest = 80

        # Act
        missing = [name for name, why in HELD["partsWithNoDocument"].items() if len(why) < shortest]

        # Assert
        self.assertEqual(missing, [])

    def test_no_independent_document_claims_to_settle_anything(self) -> None:
        # Arrange
        entries = self.entries

        # Act
        claiming = [
            entry["file"]
            for entry in entries
            if entry["rung"] != 1 and not str(entry["settles"]).startswith("Nothing")
        ]

        # Assert
        self.assertEqual(claiming, [])

    def test_no_two_documents_are_the_same_file(self) -> None:
        # Arrange
        digests = [entry["sha256"] for entry in self.entries]

        # Act
        distinct = set(digests)

        # Assert
        self.assertEqual(len(digests), len(distinct))

    def test_no_document_here_was_printed_from_a_page(self) -> None:
        # Arrange
        entries = self.entries

        # Act
        printed = [entry["file"] for entry in entries if entry.get("printedFromPage")]

        # Assert
        self.assertEqual(printed, [])

    def test_a_document_says_how_its_text_was_read(self) -> None:
        # Arrange
        entries = self.entries

        # Act
        silent = [
            entry["file"]
            for entry in entries
            if not any(way in str(entry.get("provenance", "")) for way in ("page image", "retyped"))
        ]

        # Assert
        self.assertEqual(silent, [])


class VerifyTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())

    def test_a_file_that_is_what_the_record_says_is_accepted(self) -> None:
        # Arrange
        entry = a_file(self.root, "held.pdf", b"a document")

        # Act
        verdict = documents.verify(entry, self.root)

        # Assert
        self.assertIsNone(verdict)

    def test_a_file_that_is_not_there_is_refused(self) -> None:
        # Arrange
        entry = a_file(self.root, "held.pdf", b"a document")
        (self.root / "held.pdf").unlink()

        # Act
        attempt = lambda: documents.verify(entry, self.root)  # noqa: E731

        # Assert
        self.assertRaises(documents.Refused, attempt)

    def test_a_file_with_a_different_digest_is_refused(self) -> None:
        # Arrange
        entry = a_file(self.root, "held.pdf", b"a document")
        (self.root / "held.pdf").write_bytes(b"a different one")

        # Act
        attempt = lambda: documents.verify(entry, self.root)  # noqa: E731

        # Assert
        self.assertRaises(documents.Refused, attempt)

    def test_a_file_of_the_wrong_length_is_refused_even_if_the_digest_agrees(self) -> None:
        # Arrange
        entry = a_file(self.root, "held.pdf", b"a document")
        entry["bytes"] = 1

        # Act
        attempt = lambda: documents.verify(entry, self.root)  # noqa: E731

        # Assert
        self.assertRaises(documents.Refused, attempt)


class DownloadTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())
        self.source = Path(tempfile.mkdtemp())

    def test_a_document_is_brought_down_where_the_record_names(self) -> None:
        # Arrange
        entry = a_file(self.source, "held.pdf", b"a document")
        entry["file"] = "manufacturer/held.pdf"

        # Act
        documents.download(entry, self.root)

        # Assert
        self.assertEqual((self.root / "manufacturer" / "held.pdf").read_bytes(), b"a document")

    def test_a_host_that_turns_curl_away_still_serves_the_document(self) -> None:
        # Arrange
        entry = {
            "file": "manufacturer/held.pdf",
            "rung": 1,
            "retrievedFrom": a_server_that_refuses_curl(self),
            "sha256": hashlib.sha256(b"a document").hexdigest(),
            "bytes": len(b"a document"),
        }

        # Act
        documents.download(entry, self.root)

        # Assert
        self.assertEqual((self.root / "manufacturer" / "held.pdf").read_bytes(), b"a document")

    def test_an_address_nobody_answers_is_refused(self) -> None:
        # Arrange
        entry = {
            "file": "gone.pdf",
            "rung": 1,
            "retrievedFrom": (self.source / "absent.pdf").resolve().as_uri(),
            "sha256": "0" * 64,
            "bytes": 0,
        }

        # Act
        attempt = lambda: documents.download(entry, self.root)  # noqa: E731

        # Assert
        self.assertRaises(documents.Refused, attempt)

    def test_a_fetch_that_never_answers_is_refused_rather_than_waited_on(self) -> None:
        # Arrange
        held = documents.subprocess.run

        def stall(*_args: object, **_kwargs: object) -> None:
            raise subprocess.TimeoutExpired("curl", documents.TIMEOUT)

        documents.subprocess.run = stall
        self.addCleanup(setattr, documents.subprocess, "run", held)
        entry = a_file(self.source, "held.pdf", b"a document")

        # Act
        attempt = lambda: documents.download(entry, self.root)  # noqa: E731

        # Assert
        self.assertRaises(subprocess.TimeoutExpired, attempt)


class OptionTest(unittest.TestCase):
    def test_a_run_fetches_unless_it_is_told_only_to_check(self) -> None:
        # Arrange
        argv: list[str] = []

        # Act
        check, _ = documents.options(argv)

        # Assert
        self.assertFalse(check)

    def test_checking_alone_can_be_asked_for(self) -> None:
        # Arrange
        argv = ["--check"]

        # Act
        check, _ = documents.options(argv)

        # Assert
        self.assertTrue(check)

    def test_one_document_can_be_named(self) -> None:
        # Arrange
        argv = ["--only", MANUAL]

        # Act
        _, only = documents.options(argv)

        # Assert
        self.assertEqual(only, MANUAL)

    def test_naming_nothing_after_only_is_refused(self) -> None:
        # Arrange
        argv = ["--only"]

        # Act
        attempt = lambda: documents.options(argv)  # noqa: E731

        # Assert
        self.assertRaises(SystemExit, attempt)

    def test_an_option_the_tool_does_not_know_is_refused(self) -> None:
        # Arrange
        argv = ["--everything"]

        # Act
        attempt = lambda: documents.options(argv)  # noqa: E731

        # Assert
        self.assertRaises(SystemExit, attempt)

    def test_naming_no_document_selects_all_of_them(self) -> None:
        # Arrange
        held = HELD["documents"]

        # Act
        chosen = documents.wanted(held, None)

        # Assert
        self.assertEqual(len(chosen), len(held))

    def test_naming_one_selects_only_it(self) -> None:
        # Arrange
        held = HELD["documents"]

        # Act
        chosen = documents.wanted(held, MANUAL)

        # Assert
        self.assertEqual(len(chosen), 1)


class EntryTest(unittest.TestCase):
    @override
    def setUp(self) -> None:
        self.root = Path(tempfile.mkdtemp())

    def held(self, entries: list[dict[str, Any]]) -> Path:
        path = self.root / "documents.json"
        path.write_text(json.dumps({"documents": entries}))
        return path

    def test_naming_a_document_nobody_has_is_reported_rather_than_passing(self) -> None:
        # Arrange
        argv = ["--check", "--only", "nothing-like-this"]

        # Act
        code = documents.main(argv, self.root)

        # Assert
        self.assertEqual(code, 1)

    def test_a_check_of_a_folder_that_holds_what_it_should_passes(self) -> None:
        # Arrange
        stand_in(self, [a_file(self.root, "held.pdf", b"a document")])

        # Act
        code = documents.main(["--check"], self.root)

        # Assert
        self.assertEqual(code, 0)

    def test_a_check_of_a_folder_that_does_not_fails(self) -> None:
        # Arrange
        stand_in(self, [a_file(self.root, "held.pdf", b"a document")])
        (self.root / "held.pdf").write_bytes(b"something else")

        # Act
        code = documents.main(["--check"], self.root)

        # Assert
        self.assertEqual(code, 1)

    def test_a_print_of_a_page_is_verified_and_never_fetched(self) -> None:
        # Arrange
        entry = a_file(self.root, "held.pdf", b"a document")
        entry["printedFromPage"] = True
        entry["retrievedFrom"] = "https://example.invalid/page.html"
        stand_in(self, [entry])

        # Act
        code = documents.main([], self.root)

        # Assert
        self.assertEqual(code, 0)

    def test_a_document_rendered_into_another_form_names_it(self) -> None:
        # Arrange
        entry = a_file(self.root, "held.txt", b"a document")
        entry["renderedAs"] = "held.pdf"
        stand_in(self, [entry])

        # Act
        code = documents.main(["--check"], self.root)

        # Assert
        self.assertEqual(code, 0)

    def test_a_run_that_is_not_only_checking_brings_the_document_down(self) -> None:
        # Arrange
        source = Path(tempfile.mkdtemp())
        stand_in(self, [a_file(source, "held.pdf", b"a document")])

        # Act
        code = documents.main([], self.root)

        # Assert
        self.assertEqual((code, (self.root / "held.pdf").read_bytes()), (0, b"a document"))

    def test_a_document_read_from_a_named_file_is_read_from_there(self) -> None:
        # Arrange
        path = self.held([a_file(self.root, "held.pdf", b"a document")])

        # Act
        held = documents.documents(path)

        # Assert
        self.assertEqual(held[0]["file"], "held.pdf")


class ScriptTest(unittest.TestCase):
    def test_run_as_a_script_asking_for_no_known_document_it_says_so_and_exits_1(self) -> None:
        # Arrange
        script = ROOT / "conformance" / "documents.py"

        # Act
        with (
            mock.patch.object(sys, "argv", [str(script), "--only", "no-such-document"]),
            contextlib.redirect_stdout(io.StringIO()) as said,
            self.assertRaises(SystemExit) as ended,
        ):
            runpy.run_path(str(script), run_name="__main__")

        # Assert
        self.assertEqual(
            (ended.exception.code, said.getvalue()),
            (1, "no document matches no-such-document\n"),
        )


unittest.main()
