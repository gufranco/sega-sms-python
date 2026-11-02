import functools
import itertools
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import segavdp  # noqa: E402
import smsmapper  # noqa: E402

import segasms  # noqa: E402
from segasms import speaker  # noqa: E402

PROCESSOR_HZ = 3_580_000

LOUDEST_CHANNEL = 8192

PERIOD_254_ON_TONE_ONE = (0x3E, 0x8E, 0xD3, 0x7F, 0x3E, 0x0F, 0xD3, 0x7F)

TONE_ONE_LOUDEST = (0x3E, 0x90, 0xD3, 0x7F)

OTHERS_SILENT = (0x3E, 0xBF, 0xD3, 0x7F, 0x3E, 0xDF, 0xD3, 0x7F, 0x3E, 0xFF, 0xD3, 0x7F)

LOOP = (0x18, 0xFE)

TONE = bytes((*PERIOD_254_ON_TONE_ONE, *TONE_ONE_LOUDEST, *OTHERS_SILENT, *LOOP))

FRAMES = 2


@functools.cache
def played() -> tuple[tuple[int, ...], int]:
    cartridge = smsmapper.Cartridge(TONE + bytes(0x8000 - len(TONE)))
    machine = segasms.Machine("sms", cartridge=cartridge).reset()
    for _ in range(FRAMES):
        machine.run_frame()
    return machine.speaker.take(), machine.cpu.cycles


def held_tone_on_the_left() -> segavdp.sound.Generator:
    voice = segavdp.sound.Generator(True, 1)
    for value in (0x80, 0x00, 0x90, 0xBF, 0xDF, 0xFF):
        voice.write(value)
    voice.write_stereo(0x10)
    for _ in range(16):
        voice.tick()
    return voice


def rising_edges(levels: tuple[int, ...]) -> list[int]:
    half = LOUDEST_CHANNEL // 2
    pairs = itertools.pairwise(levels)
    return [at for at, (before, after) in enumerate(pairs) if before < half <= after]


class SpeakerTest(unittest.TestCase):
    def test_a_channel_sent_left_only_sounds_on_the_left(self) -> None:
        # Arrange
        listening = speaker.Speaker(periods=1, rate=1)
        voice = held_tone_on_the_left()

        # Act
        listening.hear(voice)

        # Assert
        self.assertEqual(listening.take(), (LOUDEST_CHANNEL, 0))

    def test_five_periods_a_sample_give_one_sample_for_every_five_heard(self) -> None:
        # Arrange
        listening = speaker.Speaker(periods=5, rate=1)
        voice = held_tone_on_the_left()

        # Act
        for _ in range(10):
            listening.hear(voice)

        # Assert
        self.assertEqual(listening.take(), (LOUDEST_CHANNEL, 0) * 2)

    def test_taking_the_samples_leaves_none_behind(self) -> None:
        # Arrange
        listening = speaker.Speaker(periods=1, rate=1)
        listening.hear(held_tone_on_the_left())
        listening.take()

        # Act
        found = listening.take()

        # Assert
        self.assertEqual(found, ())


class MachineSoundTest(unittest.TestCase):
    def test_the_machine_gives_44100_stereo_samples_a_second_of_its_clock(self) -> None:
        # Arrange
        expected = played()[1] * speaker.RATE / PROCESSOR_HZ

        # Act
        samples, _ = played()

        # Assert
        self.assertLessEqual(abs(len(samples) / 2 - expected), 1)

    def test_tone_period_254_sounds_at_440_hertz(self) -> None:
        # Arrange
        hertz = PROCESSOR_HZ / (32 * 254)

        # Act
        edges = rising_edges(played()[0][0::2])

        # Assert
        samples_a_cycle = (edges[-1] - edges[0]) / (len(edges) - 1)
        self.assertAlmostEqual(speaker.RATE / samples_a_cycle, hertz, delta=1)


unittest.main()
