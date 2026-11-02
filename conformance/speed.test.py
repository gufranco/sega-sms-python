import contextlib
import io
import runpy
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from conformance import speed  # noqa: E402


def run_main(floor: int) -> tuple[int, str]:
    said = io.StringIO()
    with contextlib.redirect_stdout(said):
        code = speed.main(frames=1, repeats=1, floor=floor)
    return code, said.getvalue()


class TimedTest(unittest.TestCase):
    def test_the_median_is_the_middle_reading(self) -> None:
        # Arrange
        found = speed.Timed("check", 10, [3.0, 1.0, 2.0])

        # Act
        middle = found.median()

        # Assert
        self.assertEqual(middle, 2.0)

    def test_the_rate_is_calls_over_that_median(self) -> None:
        # Arrange
        found = speed.Timed("check", 10, [2.0])

        # Act
        rate = found.rate()

        # Assert
        self.assertEqual(rate, 5.0)

    def test_a_run_above_the_floor_beats_it(self) -> None:
        # Arrange
        found = speed.Timed("check", 10, [1.0])

        # Act
        beaten = found.beats(9)

        # Assert
        self.assertTrue(beaten)

    def test_and_one_below_it_does_not(self) -> None:
        # Arrange
        found = speed.Timed("check", 10, [1.0])

        # Act
        beaten = found.beats(11)

        # Assert
        self.assertFalse(beaten)

    def test_a_run_that_took_no_time_is_not_read_as_infinitely_fast(self) -> None:
        # Arrange
        found = speed.Timed("check", 10, [0.0])

        # Act
        rate = found.rate()

        # Assert
        self.assertEqual(rate, 0.0)


class SubjectTest(unittest.TestCase):
    def test_the_subject_is_whole_frames_of_a_cartridge_that_keeps_the_ports_busy(self) -> None:
        # Arrange
        machine = speed.busy_machine()

        # Act
        spent = speed.run(machine, 1)

        # Assert
        self.assertEqual(
            (speed.FRAMES, machine.vdp.registers[1] & 0x40, spent > 59000),
            (2, 0x40, True),
        )

    def test_a_measurement_counts_the_t_states_each_run_spent(self) -> None:
        # Arrange
        frames = 1

        # Act
        found = speed.measure(frames, repeats=2)

        # Assert
        self.assertEqual(
            (len(found.seconds), found.calls, found.what),
            (2, speed.run(speed.busy_machine(), frames), "T states through a running machine"),
        )

    def test_the_floor_sits_well_under_what_was_measured(self) -> None:
        # Arrange
        measured = speed.MEASURED_HERE

        # Act
        ratio = measured / speed.FLOOR

        # Assert
        self.assertGreaterEqual(ratio, speed.HEADROOM)


class ReportTest(unittest.TestCase):
    def test_the_report_names_the_rate_the_floor_and_the_runtime(self) -> None:
        # Arrange
        found = speed.Timed("check", 10, [1.0])

        # Act
        lines = speed.lines_for(found, floor=5)

        # Assert
        self.assertEqual(
            [("per second" in lines[0], "Python" in lines[0]), "floor: 5" in lines[1]],
            [(True, True), True],
        )

    def test_a_run_under_the_floor_says_so(self) -> None:
        # Arrange
        found = speed.Timed("check", 10, [1.0])

        # Act
        lines = speed.lines_for(found, floor=50)

        # Assert
        self.assertIn("below the floor", lines[-1])


class MainTest(unittest.TestCase):
    def test_a_run_that_beats_the_floor_reports_success(self) -> None:
        # Arrange
        floor = 1

        # Act
        code, said = run_main(floor)

        # Assert
        self.assertEqual((code, "below the floor" in said), (0, False))

    def test_a_floor_nothing_could_beat_fails_the_run(self) -> None:
        # Arrange
        floor = 10**12

        # Act
        code, said = run_main(floor)

        # Assert
        self.assertEqual((code, "below the floor" in said), (1, True))


class ScriptTest(unittest.TestCase):
    def test_run_as_a_script_it_measures_and_exits_by_the_floor(self) -> None:
        # Arrange
        script = ROOT / "conformance" / "speed.py"

        # Act
        with (
            mock.patch.object(sys, "argv", [str(script)]),
            contextlib.redirect_stdout(io.StringIO()) as said,
            self.assertRaises(SystemExit) as ended,
        ):
            runpy.run_path(str(script), run_name="__main__")

        # Assert
        self.assertEqual(
            (ended.exception.code, "T states through a running machine" in said.getvalue()),
            (0, True),
        )


unittest.main()
