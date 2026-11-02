import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import segasms  # noqa: E402
from segasms import models  # noqa: E402


class PartTest(unittest.TestCase):
    def test_each_console_carries_the_vdp_its_board_does(self) -> None:
        # Arrange
        names = ("mark-iii", "sms", "sms2", "gg")

        # Act
        parts = [models.vdp_part(name) for name in names]

        # Assert
        self.assertEqual(parts, ["315-5124", "315-5124", "315-5246", "315-5378"])

    def test_an_alias_the_board_accepts_reaches_the_same_part(self) -> None:
        # Arrange
        alias = "Game Gear"

        # Act
        part = models.vdp_part(alias)

        # Assert
        self.assertEqual(part, "315-5378")

    def test_an_unknown_console_names_the_ones_there_are(self) -> None:
        # Arrange
        asked = "neo geo"

        # Act
        with self.assertRaises(segasms.UnknownModelError) as caught:
            models.vdp_part(asked)

        # Assert
        self.assertIn("'sms2'", str(caught.exception))


class RecordTest(unittest.TestCase):
    def test_each_machine_names_its_console_its_vdp_and_its_processor(self) -> None:
        # Arrange
        names = sorted(segasms.MODELS)

        # Act
        records = [
            (model.console, model.vdp, model.processor)
            for model in (segasms.MODELS[name] for name in names)
        ]

        # Assert
        self.assertEqual(
            (names, records),
            (
                ["gg", "mark-iii", "sms", "sms2"],
                [
                    ("gg", "315-5378", "z80"),
                    ("mark-iii", "315-5124", "z80"),
                    ("sms", "315-5124", "z80"),
                    ("sms2", "315-5246", "z80"),
                ],
            ),
        )


class NameTest(unittest.TestCase):
    def test_each_record_answers_to_its_console_name_and_the_board_s_aliases(self) -> None:
        # Arrange
        names = ("mark-iii", "sms", "sms2", "gg")

        # Act
        held = [(segasms.MODELS[name].name, segasms.MODELS[name].aliases) for name in names]

        # Assert
        self.assertEqual(
            held,
            [
                ("mark-iii", ("mark3", "markiii", "sg-1000 mark iii")),
                ("sms", ("master system", "sms1", "master-system")),
                ("sms2", ("master system ii", "master-system-ii")),
                ("gg", ("game gear", "game-gear", "gamegear")),
            ],
        )


class RegionTest(unittest.TestCase):
    def test_a_european_master_system_runs_pal_and_the_rest_ntsc(self) -> None:
        # Arrange
        asked = (("sms", "europe"), ("sms", "usa"), ("sms2", "japan"), ("gg", "europe"))

        # Act
        regions = [models.vdp_region(name, region) for name, region in asked]

        # Assert
        self.assertEqual(regions, ["pal", "ntsc", "ntsc", "ntsc"])


unittest.main()
