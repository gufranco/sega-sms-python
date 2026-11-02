import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import segavdp  # noqa: E402
import smsmapper  # noqa: E402

from segasms import bus  # noqa: E402


def wired(model: str) -> tuple[bus.Ports, smsmapper.Console, segavdp.core.Chip]:
    console = smsmapper.Console(model)
    vdp = segavdp.Chip({"sms": "315-5124", "gg": "315-5378"}[model]).reset()
    return bus.Ports(console, vdp), console, vdp


class MemoryTest(unittest.TestCase):
    def test_a_write_lands_in_system_ram_and_reads_back(self) -> None:
        # Arrange
        memory = bus.Memory(smsmapper.Console("sms"))
        memory.write8(0xC123, 0x5A)

        # Act
        held = memory.read8(0xE123)

        # Assert
        self.assertEqual(held, 0x5A)


class PortsTest(unittest.TestCase):
    def test_a_control_port_write_reaches_the_vdp(self) -> None:
        # Arrange
        ports, _, vdp = wired("sms")

        # Act
        for value in (0x33, 0x82):
            ports.write(0xBF, value)

        # Assert
        self.assertEqual(vdp.registers[2], 0x33)

    def test_the_status_read_comes_from_the_vdp(self) -> None:
        # Arrange
        ports, _, vdp = wired("sms")
        vdp.run_dots(342 * 200)

        # Act
        read = ports.read(0xBF)

        # Assert
        self.assertEqual((read & 0x80, vdp.status & 0x80), (0x80, 0x00))

    def test_th_rising_as_an_output_latches_the_h_counter(self) -> None:
        # Arrange
        ports, _, vdp = wired("sms")
        ports.write(0x3F, 0x55)
        vdp.run_dots(100)
        before = vdp.read_h_counter()

        # Act
        ports.write(0x3F, 0xF5)

        # Assert
        self.assertNotEqual(vdp.read_h_counter(), before)

    def test_a_write_that_leaves_th_alone_latches_nothing(self) -> None:
        # Arrange
        ports, _, vdp = wired("sms")
        ports.write(0x3F, 0xF5)
        vdp.run_dots(100)
        before = vdp.read_h_counter()

        # Act
        ports.write(0x3F, 0xF5)

        # Assert
        self.assertEqual(vdp.read_h_counter(), before)

    def test_port_6_on_a_game_gear_sets_the_stereo_register_and_the_board_keeps_it(self) -> None:
        # Arrange
        ports, console, vdp = wired("gg")

        # Act
        ports.write(0x06, 0x0F)

        # Assert
        self.assertEqual((vdp.sound.stereo, console.registers[6]), (0x0F, 0x0F))

    def test_the_game_gear_start_button_reads_through_port_0(self) -> None:
        # Arrange
        ports, console, _ = wired("gg")
        console.press("start")

        # Act
        read = ports.read(0x00)

        # Assert
        self.assertEqual(read & 0x80, 0x00)


unittest.main()
