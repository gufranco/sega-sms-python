import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import bench  # noqa: E402


class RecordTest(unittest.TestCase):
    def test_the_facts_and_the_unstated_values_come_from_one_record(self) -> None:
        # Arrange
        held = json.loads((ROOT / "conformance" / "hardware.json").read_text())

        # Act
        found = (bench.HELD, bench.FACTS, bench.UNSTATED)

        # Assert
        self.assertEqual(found, (held, held["facts"], held["notStated"]))


unittest.main()
