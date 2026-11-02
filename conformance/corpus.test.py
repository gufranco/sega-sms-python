import contextlib
import io
import json
import runpy
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import corpus  # noqa: E402

DIGEST = "a" * 64

CHAIN = "b" * 64


def sound(**changed: Any) -> dict[str, Any]:
    held: dict[str, Any] = {
        "listings": 3,
        "images": 2,
        "gated": 1,
        "frames": 300,
        "pal": 1,
        "properties": {"raises": 0, "draws": 0},
        "drew": {"0": 1, "4": 1},
        "runs": {DIGEST: [0, CHAIN], "c" * 64: [4, CHAIN]},
    }
    held.update(changed)
    return held


def kept(held: dict[str, Any]) -> Path:
    where = Path(tempfile.mkdtemp()) / "corpus.json"
    where.write_text(json.dumps(held))
    return where


def run_main(where: Path) -> tuple[int, str]:
    with contextlib.redirect_stdout(io.StringIO()) as said:
        code = corpus.main(where)
    return code, said.getvalue()


class ConsistencyTest(unittest.TestCase):
    def test_a_sound_corpus_has_nothing_wrong_with_it(self) -> None:
        # Arrange
        held = sound()

        # Act
        found = corpus.inconsistent(held)

        # Assert
        self.assertEqual(found, [])

    def test_a_run_count_other_than_the_image_count_is_named(self) -> None:
        # Arrange
        held = sound(runs={DIGEST: [0, CHAIN]})

        # Act
        found = corpus.inconsistent(held)

        # Assert
        self.assertIn("1 runs for 2 images", found)

    def test_more_first_drawn_frames_than_images_is_named(self) -> None:
        # Arrange
        held = sound(drew={"0": 3})

        # Act
        found = corpus.inconsistent(held)

        # Assert
        self.assertIn("3 images drew of 2", found)

    def test_a_first_drawn_frame_past_the_bound_is_named(self) -> None:
        # Arrange
        held = sound(drew={"0": 1, "300": 1})

        # Act
        found = corpus.inconsistent(held)

        # Assert
        self.assertIn("an image drew first at frame 300 of 300", found)

    def test_a_count_larger_than_the_images_is_named(self) -> None:
        # Arrange
        held = sound(pal=5)

        # Act
        found = corpus.inconsistent(held)

        # Assert
        self.assertIn("pal is 5 of 2 images", found)

    def test_a_run_whose_first_frame_disagrees_with_the_tally_is_named(self) -> None:
        # Arrange
        held = sound(runs={DIGEST: [0, CHAIN], "c" * 64: [5, CHAIN]})

        # Act
        found = corpus.inconsistent(held)

        # Assert
        self.assertIn("the runs' first drawn frames do not add up to the tally", found)


class MainTest(unittest.TestCase):
    def test_a_sound_corpus_replays_and_exits_0(self) -> None:
        # Arrange
        where = kept(sound())

        # Act
        code, said = run_main(where)

        # Assert
        self.assertEqual(
            (code, said.splitlines()[0]),
            (0, "2 images, 1 retail, 300 frames each, 2 drew"),
        )

    def test_a_broken_property_fails_the_replay(self) -> None:
        # Arrange
        where = kept(sound(properties={"raises": 0, "draws": 1}))

        # Act
        code, said = run_main(where)

        # Assert
        self.assertEqual((code, "   !  draws: 1 broken" in said), (1, True))

    def test_an_inconsistent_corpus_fails_and_says_why(self) -> None:
        # Arrange
        where = kept(sound(pal=5))

        # Act
        code, said = run_main(where)

        # Assert
        self.assertEqual((code, "     !  pal is 5 of 2 images" in said), (1, True))


class ScriptTest(unittest.TestCase):
    def test_run_as_a_script_on_a_named_corpus_it_replays_that_one(self) -> None:
        # Arrange
        script = ROOT / "conformance" / "corpus.py"
        where = kept(sound())

        # Act
        with (
            mock.patch.object(sys, "argv", [str(script), str(where)]),
            contextlib.redirect_stdout(io.StringIO()),
            self.assertRaises(SystemExit) as ended,
        ):
            runpy.run_path(str(script), run_name="__main__")

        # Assert
        self.assertEqual(ended.exception.code, 0)


unittest.main()
