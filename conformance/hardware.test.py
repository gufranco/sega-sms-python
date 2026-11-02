import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import smsmapper  # noqa: E402

import segasms  # noqa: E402
from conformance.bench import FACTS  # noqa: E402

LOOP = bytes([0x18, 0xFE])

STACK = 0xDFF0


def running(code: bytes, model: str = "sms") -> segasms.Machine:
    image = code + bytes(0x8000 - len(code))
    machine = segasms.Machine(model, cartridge=smsmapper.Cartridge(image)).reset()
    machine.cpu.registers.sp = STACK
    return machine


def enabling(register: int, value: int) -> bytes:
    return bytes([0x3E, value, 0xD3, 0xBF, 0x3E, 0x80 | register, 0xD3, 0xBF])


INTERRUPT_MODE_1_THEN_ENABLE = bytes([0xED, 0x56])

ENABLE_INTERRUPTS_AND_WAIT = bytes([0xFB, 0x18, 0xFE])


class NonMaskableTest(unittest.TestCase):
    def test_pause_drives_the_non_maskable_interrupt_to_its_restart(self) -> None:
        # Arrange
        fact = FACTS["pauseIsNmi"]["value"]
        machine = running(LOOP)
        machine.press(fact["button"])

        # Act
        machine.step()

        # Assert
        self.assertEqual(machine.cpu.registers.pc, int(fact["restart"], 16))

    def test_holding_pause_gives_one_interrupt_only(self) -> None:
        # Arrange
        fact = FACTS["nmiEdgeTriggered"]["value"]
        machine = running(LOOP)
        machine.press("pause")

        # Act
        reached = [machine.step() and machine.cpu.registers.pc for _ in range(200)]

        # Assert
        self.assertEqual(reached.count(0x66), fact["interruptsWhileHeld"])


class MaskableTest(unittest.TestCase):
    def test_the_frame_interrupt_restarts_the_processor_at_0038(self) -> None:
        # Arrange
        fact = FACTS["intFromVdp"]["value"]
        program = INTERRUPT_MODE_1_THEN_ENABLE + enabling(1, 0x20) + ENABLE_INTERRUPTS_AND_WAIT
        machine = running(program)

        # Act
        machine.cpu.run_until(
            lambda part: part.registers.pc == int(fact["restart"], 16), limit=20000
        )

        # Assert
        self.assertEqual(machine.vdp.status & 0x80, 0x80)

    def test_the_line_counter_restarts_the_processor_at_0038_as_well(self) -> None:
        # Arrange
        fact = FACTS["intFromVdp"]["value"]
        program = (
            INTERRUPT_MODE_1_THEN_ENABLE
            + enabling(10, 0x00)
            + enabling(0, 0x14)
            + ENABLE_INTERRUPTS_AND_WAIT
        )
        machine = running(program)

        # Act
        machine.cpu.run_until(
            lambda part: part.registers.pc == int(fact["restart"], 16), limit=20000
        )

        # Assert
        self.assertEqual((machine.vdp.registers[1] & 0x20, machine.vdp.interrupt), (0x00, True))


class ResetButtonTest(unittest.TestCase):
    def test_the_reset_button_is_read_on_a_port_and_resets_nothing(self) -> None:
        # Arrange
        fact = FACTS["resetButtonIsAnInput"]["value"]
        machine = running(bytes([0xDB, int(fact["port"], 16), 0x18, 0xFE]))
        machine.press("reset")

        # Act
        machine.step()

        # Assert
        self.assertEqual(
            (machine.cpu.registers.a & (1 << fact["bit"]), machine.cpu.registers.pc),
            (0, 2),
        )


class ClockTest(unittest.TestCase):
    def test_a_second_of_sound_is_the_printed_clock_in_t_states(self) -> None:
        # Arrange
        hertz = FACTS["processorClock"]["value"]["megahertz"] * 1_000_000
        machine = running(LOOP)
        machine.run_frame()

        # Act
        samples = machine.speaker.take()

        # Assert
        expected = machine.cpu.cycles * segasms.speaker.RATE / hertz
        self.assertLessEqual(abs(len(samples) / 2 - expected), 1)


unittest.main()
