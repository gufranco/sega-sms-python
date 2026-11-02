from __future__ import annotations

import importlib
import re
import sys
import types
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any, ClassVar

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from conformance.family_member import (
    PACKAGE,
    ROOT,
)

SURFACE = (
    "Cpu",
    "MODELS",
    "UNSET_SEED",
    "Clock",
    "ClockClosed",
    "RunLimit",
    "UnknownModelError",
)


PART_SURFACE = (
    "Chip",
    "MODELS",
    "Model",
    "UnknownModelError",
)


def buildable_variants(package: Any = None, variants: Any = None) -> list[str]:
    known = VARIANTS if variants is None else variants
    asked = getattr(PACKAGE if package is None else package, "available", None)
    if not callable(asked):
        return sorted(known)
    held = asked()
    if not isinstance(held, Mapping):
        return sorted(known)
    return sorted(name for name in known if name in held)


class BuildableVariantTest(unittest.TestCase):
    NAMED: ClassVar[dict[str, object]] = {"one": object(), "two": object()}

    class Silent:
        pass

    class Odd:
        @staticmethod
        def available() -> int:
            return 7

    class Partial:
        @staticmethod
        def available() -> dict[str, int]:
            return {"two": 1}

    def test_a_member_that_publishes_no_catalogue_can_build_everything_it_names(self) -> None:
        # Arrange
        member = self.Silent()

        # Act
        found = buildable_variants(member, self.NAMED)

        # Assert
        self.assertEqual(found, ["one", "two"])

    def test_and_so_can_one_whose_catalogue_is_not_a_mapping(self) -> None:
        # Arrange
        member = self.Odd()

        # Act
        found = buildable_variants(member, self.NAMED)

        # Assert
        self.assertEqual(found, ["one", "two"])

    def test_a_member_holding_one_file_can_build_that_one(self) -> None:
        # Arrange
        member = self.Partial()

        # Act
        found = buildable_variants(member, self.NAMED)

        # Assert
        self.assertEqual(found, ["two"])


def public_exceptions() -> list[str]:
    errors = importlib.import_module(f"{PACKAGE.__name__}.errors")
    return [
        name
        for name, held in vars(errors).items()
        if isinstance(held, type)
        and issubclass(held, Exception)
        and not name.startswith("_")
        and held.__module__ == errors.__name__
    ]


class PublishedSurfaceTest(unittest.TestCase):
    def test_and_so_is_everything_it_can_raise(self) -> None:
        # Arrange
        published = PACKAGE.__all__

        # Act
        public = public_exceptions()

        # Assert
        self.assertGreater(len(public), 0, "the errors module defines no exception")
        self.assertEqual([name for name in public if name not in published], [])

    def test_nothing_is_promised_that_is_not_there(self) -> None:
        # Arrange
        promised = PACKAGE.__all__

        # Act
        absent = [name for name in promised if not hasattr(PACKAGE, name)]

        # Assert
        self.assertEqual(absent, [])


def catalogue(package: Any = None) -> dict[str, Any]:
    held = PACKAGE if package is None else package
    for name in sorted(getattr(held, "__all__", ())):
        found = getattr(held, name, None)
        if not isinstance(found, dict) or not found:
            continue
        if all(hasattr(one, "name") and hasattr(one, "aliases") for one in found.values()):
            return dict(found)
    return {}


VARIANTS: dict[str, Any] = catalogue()


def built(name: str, readme: str) -> bool:
    return re.search(rf"""\w\(\s*["']{re.escape(name)}["']""", readme) is not None


@unittest.skipUnless(VARIANTS, "this package names no variants")
class DocumentedModelTest(unittest.TestCase):
    def test_every_model_has_a_worked_construction(self) -> None:
        # Arrange
        readme = (ROOT / "README.md").read_text()

        # Act
        undocumented = [name for name in VARIANTS if not built(name, readme)]

        # Assert
        self.assertEqual(undocumented, [])

    def test_and_every_alias_is_named_beside_it(self) -> None:
        # Arrange
        readme = (ROOT / "README.md").read_text()

        # Act
        unnamed = [
            alias for model in VARIANTS.values() for alias in model.aliases if alias not in readme
        ]

        # Assert
        self.assertEqual(unnamed, [])

    def test_the_reader_of_that_tells_a_call_from_a_mention(self) -> None:
        # Arrange
        lines = ('Chip("a-part")', "Cpu('a-part')", "the a-part is covered here", "`a-part`")

        # Act
        found = [built("a-part", line) for line in lines]

        # Assert
        self.assertEqual(found, [True, True, False, False])


class CatalogueReaderTest(unittest.TestCase):
    def package(self, **published: Any) -> Any:
        held: Any = types.ModuleType("published")
        held.__all__ = sorted(published)
        for name, one in published.items():
            setattr(held, name, one)
        return held

    def variant(self, name: str) -> Any:
        return type("Variant", (), {"name": name, "aliases": ()})()

    def test_it_finds_a_catalogue_whatever_the_package_calls_it(self) -> None:
        # Arrange
        held = self.package(FORMATS={"4bpp": self.variant("4bpp")})

        # Act
        found = sorted(catalogue(held))

        # Assert
        self.assertEqual(found, ["4bpp"])

    def test_and_finds_it_under_any_other_name(self) -> None:
        # Arrange
        held = self.package(MODELS={"z80": self.variant("z80")})

        # Act
        found = sorted(catalogue(held))

        # Assert
        self.assertEqual(found, ["z80"])

    def test_it_steps_over_a_published_name_that_is_not_a_mapping(self) -> None:
        # Arrange
        held = self.package(LIMIT=3, MODELS={"z80": self.variant("z80")})

        # Act
        found = sorted(catalogue(held))

        # Assert
        self.assertEqual(found, ["z80"])

    def test_and_over_a_mapping_with_nothing_in_it(self) -> None:
        # Arrange
        held = self.package(EMPTY={}, MODELS={"z80": self.variant("z80")})

        # Act
        found = sorted(catalogue(held))

        # Assert
        self.assertEqual(found, ["z80"])

    def test_and_over_a_mapping_whose_entries_are_not_variants(self) -> None:
        # Arrange
        held = self.package(SIZES={"small": 8, "large": 64})

        # Act
        found = catalogue(held)

        # Assert
        self.assertEqual(found, {})

    def test_a_package_publishing_no_catalogue_answers_with_nothing(self) -> None:
        # Arrange
        held = self.package(decode=len)

        # Act
        found = catalogue(held)

        # Assert
        self.assertEqual(found, {})

    def test_and_so_does_one_publishing_nothing_at_all(self) -> None:
        # Arrange
        held = types.ModuleType("bare")

        # Act
        found = catalogue(held)

        # Assert
        self.assertEqual(found, {})


unittest.main()
