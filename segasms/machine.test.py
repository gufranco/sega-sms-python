import copy
import sys
import unittest
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import segavdp  # noqa: E402
import smsmapper  # noqa: E402

import segasms  # noqa: E402

IMAGE_SIZE = 0x8000


def cartridge(code: bytes) -> smsmapper.Board:
    return smsmapper.Cartridge(code + bytes(IMAGE_SIZE - len(code)))


def running(code: bytes, model: str = "sms") -> segasms.Machine:
    machine = segasms.Machine(model, cartridge=cartridge(code))
    machine.reset()
    return machine


OPCODE_AND_OPERAND_STATES = 7

STROBE_TICKS_INTO_THE_IO_CYCLE = 10

OUT_STROBE_TICKS = OPCODE_AND_OPERAND_STATES * 3 + STROBE_TICKS_INTO_THE_IO_CYCLE

IO_CYCLE_START_TICKS = OPCODE_AND_OPERAND_STATES * 3

POISE_LIMIT = 0x400

TH_TOGGLE = bytes([0x3E, 0x55, 0xD3, 0x3F, 0x3E, 0xF5, 0xD3, 0x3F, 0x18, 0xF6])

SLED_START = 0x0100

SLED_END = 0x3C00

SETUP = bytes([0xF3, 0xED, 0x56, 0x3E, 0x20, 0xD3, 0xBF, 0x3E, 0x81, 0xD3, 0xBF, 0xC3, 0x00, 0x01])

PENDING_THEN_STATUS_READ = (
    SETUP
    + bytes(0x38 - len(SETUP))
    + bytes([0x18, 0xFE])
    + bytes(SLED_START - 0x3A)
    + bytes(SLED_END - SLED_START)
    + bytes([0xFB, 0xDB, 0xBF, 0x18, 0xFE])
)


def after(vdp: segavdp.core.Chip, ticks: int, read: Callable[[segavdp.core.Chip], int]) -> int:
    probe = copy.deepcopy(vdp)
    for _ in range(ticks):
        probe.tick()
    return read(probe)


def latched_h_counter(vdp: segavdp.core.Chip) -> int:
    vdp.latch_h_counter()
    return vdp.read_h_counter()


def v_counter(vdp: segavdp.core.Chip) -> int:
    return vdp.read_v_counter()


def straddles(machine: segasms.Machine, read: Callable[[segavdp.core.Chip], int]) -> bool:
    return after(machine.vdp, IO_CYCLE_START_TICKS, read) != after(
        machine.vdp, OUT_STROBE_TICKS, read
    )


def poised(machine: segasms.Machine, read: Callable[[segavdp.core.Chip], int]) -> None:
    found = any(straddles(machine, read) or machine.step() < 0 for _ in range(POISE_LIMIT))
    assert found


class ClockTest(unittest.TestCase):
    def test_each_t_state_moves_the_vdp_three_ticks(self) -> None:
        # Arrange
        machine = running(bytes([0x00, 0x00]))
        before = (machine.cpu.cycles, machine.vdp.cycles)

        # Act
        spent = machine.step()

        # Assert
        self.assertEqual(
            (spent, machine.cpu.cycles - before[0], machine.vdp.cycles - before[1]), (4, 4, 12)
        )


class PowerOnTest(unittest.TestCase):
    def test_a_cleared_machine_starts_with_zeroed_video_and_colour_ram(self) -> None:
        # Arrange
        image = cartridge(bytes([0x18, 0xFE]))

        # Act
        machine = segasms.Machine("gg", cartridge=image, cleared=True).reset()

        # Assert
        self.assertEqual(
            (
                {machine.vdp.memory.read8(address) for address in range(0x4000)},
                set(machine.vdp.cram.entries()),
            ),
            ({0}, {0}),
        )

    def test_a_cleared_machine_starts_with_every_vdp_register_zero(self) -> None:
        # Arrange
        image = cartridge(bytes([0x18, 0xFE]))

        # Act
        machine = segasms.Machine("sms", cartridge=image, cleared=True).reset()

        # Assert
        self.assertEqual(set(machine.vdp.registers), {0})

    def test_by_default_the_power_on_contents_are_scrambled_as_on_hardware(self) -> None:
        # Arrange
        image = cartridge(bytes([0x18, 0xFE]))

        # Act
        machine = segasms.Machine("sms", cartridge=image).reset()

        # Assert
        self.assertGreater(len(set(machine.vdp.cram.entries())), 1)


class HandOverTest(unittest.TestCase):
    def test_a_master_system_starts_where_the_export_bios_hands_over(self) -> None:
        # Arrange
        machine = running(bytes([0x18, 0xFE]))

        # Act
        machine.handed_over()

        # Assert
        self.assertEqual((machine.cpu.registers.sp, machine.console.read(0xC000)), (0xDFF0, 0xAB))

    def test_a_game_gear_keeps_its_reset_values(self) -> None:
        # Arrange
        machine = running(bytes([0x18, 0xFE]), model="gg")
        before = (machine.cpu.registers.sp, machine.console.read(0xC000))

        # Act
        machine.handed_over()

        # Assert
        self.assertEqual((machine.cpu.registers.sp, machine.console.read(0xC000)), before)


class PortTest(unittest.TestCase):
    def test_two_writes_to_bf_set_a_vdp_register(self) -> None:
        # Arrange
        machine = running(bytes([0x3E, 0x5A, 0xD3, 0xBF, 0x3E, 0x87, 0xD3, 0xBF]))

        # Act
        for _ in range(4):
            machine.step()

        # Assert
        self.assertEqual(machine.vdp.registers[7], 0x5A)

    def test_a_write_to_3e_reaches_the_board(self) -> None:
        # Arrange
        machine = running(bytes([0x3E, 0xEB, 0xD3, 0x3E]))

        # Act
        for _ in range(2):
            machine.step()

        # Assert
        self.assertEqual(machine.console.memory.control, 0xEB)

    def test_a_read_of_7e_gives_the_v_counter(self) -> None:
        # Arrange
        machine = running(bytes([0xDB, 0x7E]))

        # Act
        machine.step()

        # Assert
        self.assertEqual(machine.cpu.registers.a, machine.vdp.read_v_counter())

    def test_a_read_of_dc_gives_the_first_controller(self) -> None:
        # Arrange
        machine = running(bytes([0xDB, 0xDC]))
        machine.press("up")

        # Act
        machine.step()

        # Assert
        self.assertEqual(machine.cpu.registers.a, 0xFE)


class StrobeTest(unittest.TestCase):
    def test_a_port_write_lands_where_the_write_strobe_ends(self) -> None:
        # Arrange
        machine = running(TH_TOGGLE)
        for _ in range(3):
            machine.step()
        expected = after(machine.vdp, OUT_STROBE_TICKS, latched_h_counter)

        # Act
        machine.step()

        # Assert
        self.assertEqual(machine.vdp.read_h_counter(), expected)

    def test_a_port_read_takes_the_value_where_the_read_strobe_ends(self) -> None:
        # Arrange
        machine = running(bytes([0xDB, 0x7E]) * 0x400)
        poised(machine, v_counter)
        expected = after(machine.vdp, OUT_STROBE_TICKS, v_counter)

        # Act
        machine.step()

        # Assert
        self.assertEqual(machine.cpu.registers.a, expected)

    def test_an_instruction_with_a_port_access_still_moves_the_vdp_three_ticks_a_state(
        self,
    ) -> None:
        # Arrange
        machine = running(bytes([0xD3, 0xBF]))
        before = machine.vdp.cycles

        # Act
        spent = machine.step()

        # Assert
        self.assertEqual((spent, machine.vdp.cycles - before), (11, 33))

    def test_an_interrupt_the_status_read_clears_is_still_taken_after_it(self) -> None:
        # Arrange
        machine = running(PENDING_THEN_STATUS_READ)
        machine.cpu.registers.sp = 0xDFF0
        machine.cpu.run_until(lambda part: part.registers.pc == SLED_END, limit=20_000)
        machine.step()

        # Act
        machine.step()

        # Assert
        self.assertEqual(machine.cpu.registers.pc, 0x0038)


class MasterSystemModeTest(unittest.TestCase):
    def test_a_game_gear_in_master_system_mode_drops_a_write_to_port_2(self) -> None:
        # Arrange
        image = cartridge(bytes([0x3E, 0xFF, 0xD3, 0x02, 0x18, 0xFE]))
        machine = segasms.Machine("gg", cartridge=image, handheld_mode=False).reset()
        before = machine.console.memory.control

        # Act
        for _ in range(2):
            machine.step()

        # Assert
        self.assertEqual(machine.console.memory.control, before)

    def test_only_a_game_gear_in_its_own_mode_shows_its_window(self) -> None:
        # Arrange
        image = cartridge(bytes([0x18, 0xFE]))
        built = [
            segasms.Machine("gg", cartridge=image),
            segasms.Machine("gg", cartridge=image, handheld_mode=False),
            segasms.Machine("sms", cartridge=image),
        ]

        # Act
        found = [(one.windowed(), one.vdp.handheld_mode) for one in built]

        # Assert
        self.assertEqual(found, [(True, True), (False, False), (False, False)])


class InterruptTest(unittest.TestCase):
    def test_the_frame_interrupt_restarts_the_processor_at_0038(self) -> None:
        # Arrange
        program = bytes([0xED, 0x56, 0x3E, 0x20, 0xD3, 0xBF, 0x3E, 0x81, 0xD3, 0xBF, 0xFB])
        machine = running(program + bytes([0x18, 0xFE]))
        machine.cpu.registers.sp = 0xDFF0

        # Act
        machine.cpu.run_until(lambda part: part.registers.pc == 0x0038, limit=20000)

        # Assert
        self.assertEqual(
            (machine.vdp.status & 0x80, machine.cpu.registers.iff1, machine.vdp.interrupt),
            (0x80, False, True),
        )

    def test_pause_takes_the_non_maskable_interrupt_once(self) -> None:
        # Arrange
        machine = running(bytes([0x18, 0xFE]))
        machine.cpu.registers.sp = 0xDFF0
        machine.press("pause")

        # Act
        seen = [machine.step() and machine.cpu.registers.pc for _ in range(3)]

        # Assert
        self.assertEqual(seen.count(0x0066), 1)


unittest.main()
