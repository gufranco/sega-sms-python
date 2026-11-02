from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.family_member import (
    FAMILY,
    KIND,
    ROOT,
)


class ModelsAClockedPartTest(unittest.TestCase):
    def row(self) -> str:
        pattern = rf"^\|\s*\[{re.escape(ROOT.name)}\]\([^)]*\)\s*\|(.+)\|(.+)\|\s*$"
        found = re.search(pattern, FAMILY, re.M)

        assert found is not None, f"{ROOT.name} is not in the membership table"
        return found.group(2).strip()

    def test_this_member_is_in_the_membership_table(self) -> None:
        # Arrange
        member = ROOT.name

        # Act
        standard = (ROOT / "FAMILY.md").read_text()

        # Assert
        self.assertIn(member, standard)

    def test_and_the_kind_it_declares_is_the_kind_the_table_gives_it(self) -> None:
        # Arrange
        declared = KIND

        # Act
        given = self.row()

        # Assert
        self.assertEqual(declared, given)

    def test_the_table_only_uses_kinds_the_standard_explains(self) -> None:
        # Arrange
        explained = {"Clocked part", "Part", "Board", "Format", "Tool"}

        # Act
        kinds = set(re.findall(r"\|\s*(Clocked part|Part|Board|Format|Tool)\s*\|", FAMILY))

        # Assert
        self.assertLessEqual(kinds, explained)
        self.assertIn(KIND, kinds)

    def test_the_standard_says_what_a_kind_that_is_not_clocked_skips(self) -> None:
        # Arrange
        sentence = "skips the section about a clock"

        # Act
        standard = (ROOT / "FAMILY.md").read_text()

        # Assert
        self.assertIn(sentence, standard)


unittest.main()
