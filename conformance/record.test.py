import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import segasms  # noqa: E402
from conformance.bench import FACTS, HELD, UNSTATED  # noqa: E402


class DocumentTest(unittest.TestCase):
    def test_every_fact_names_a_document_the_record_declares(self) -> None:
        # Arrange
        declared = set(HELD["documents"])

        # Act
        unnamed = [name for name, fact in FACTS.items() if fact["document"] not in declared]

        # Assert
        self.assertEqual(unnamed, [])

    def test_every_fact_names_a_printed_page(self) -> None:
        # Arrange
        facts = FACTS

        # Act
        unpaged = [
            name
            for name, fact in facts.items()
            if not all(
                part.isdigit() for part in str(fact.get("page", "")).replace(",", " ").split()
            )
            or not str(fact.get("page", "")).strip()
        ]

        # Assert
        self.assertEqual(unpaged, [])

    def test_every_entry_governs_parts_the_package_models(self) -> None:
        # Arrange
        entries = {**FACTS, **UNSTATED}

        # Act
        stray = [
            name
            for name, entry in entries.items()
            if not entry.get("governs") or not set(entry["governs"]) <= set(segasms.MODELS)
        ]

        # Assert
        self.assertEqual(stray, [])

    def test_the_record_and_the_document_list_name_the_same_file(self) -> None:
        # Arrange
        listed = json.loads((ROOT / "conformance" / "documents.json").read_text())

        # Act
        digests = {entry["sha256"] for entry in listed["documents"]}

        # Assert
        self.assertLessEqual({one["sha256"] for one in HELD["documents"].values()}, digests)

    def test_every_unstated_value_is_marked_and_says_how_to_settle_it(self) -> None:
        # Arrange
        entries = UNSTATED

        # Act
        loose = [
            name
            for name, entry in entries.items()
            if entry.get("verified") is not False
            or not entry.get("howToSettleIt")
            or not entry.get("source")
        ]

        # Assert
        self.assertEqual(loose, [])


unittest.main()
