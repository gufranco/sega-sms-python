# Sega SMS

The Sega Mark III, both Master Systems and the Game Gear in Python: the Z80, the VDP package with its sound generator and the board on one clock, booting the original BIOS and a real cartridge, and giving the frame the VDP drew, dot by dot.

English | [日本語](README.ja.md) | [简体中文](README.zh-Hans.md) | [繁體中文（香港）](README.zh-HK.md)

[![CI](https://github.com/gufranco/sega-sms-python/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/sega-sms-python/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/gufranco/sega-sms-python)](https://github.com/gufranco/sega-sms-python/releases)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**2,608** distinct Master System and Game Gear images booted for **300** frames each, **0** property failures over the **813** retail ones, **5** quotes located in the manual, **695** tests, **100%** statement and branch coverage with nothing excluded, no dependencies beyond the standard library and three members of this family

```python
import smsmapper
import segasms

program = bytes(
    [0x3E, 0x04, 0xD3, 0xBF, 0x3E, 0x80, 0xD3, 0xBF]
    + [0x3E, 0x01, 0xD3, 0xBF, 0x3E, 0x87, 0xD3, 0xBF]
    + [0x3E, 0x11, 0xD3, 0xBF, 0x3E, 0xC0, 0xD3, 0xBF]
    + [0x3E, 0x3F, 0xD3, 0xBE, 0x18, 0xFE]
)
cartridge = smsmapper.Cartridge(program + bytes(0x8000 - len(program)))
machine = segasms.Machine("sms", cartridge=cartridge).reset()

first = machine.run_frame()
second = machine.run_frame()
print(first.width, first.height, len(second.colours), sorted(set(second.colours)))
print(machine.vdp.model, machine.vdp.region, machine.cpu.model)
print(second.digest()[:16])

spent = machine.step()
print(spent, machine.cpu.registers.pc)
```

```
256 192 49152 [63]
315-5124 ntsc z80
f927d1a55081d857
12 28
```

The program puts the VDP in mode 4, makes colour RAM entry 17 the backdrop, and writes white, 3Fh, into it. The display stays off, so every one of the 256 by 192 active dots shows the backdrop. A frame is the colour RAM word of each active dot in the order the beam draws them, and its digest is SHA-256 over those words. The last instruction is the `jr` the program ends on, 12 T states.

## Install

| Requirement | Why                                             |
| :---------- | :---------------------------------------------- |
| Docker      | Runs everything: Python, the tools, tests       |
| git         | Fetches the repository and its members          |
| uv          | Only for `scripts/play`, the window on the host |

```bash
git clone --recurse-submodules https://github.com/gufranco/sega-sms-python.git
cd sega-sms-python
scripts/run python segasms/doctor.py
```

On Windows, run `scripts\run.ps1` in place of `scripts/run`. The first run builds the image, which pins Python, uv, Node and every tool; nothing else is installed on the machine. `scripts/run <command>` runs any command in it with the checkout mounted. The package needs nothing beyond the standard library and three members of this family, which the clone brings as submodules: `zilog-z80-python`, `sega-vdp-python` and `sms-mapper-python`. The window, `window.play`, sits outside the package and also needs pygame-ce. A source archive from the download-zip link carries no submodule and cannot run.

The doctor checks the container, the mounted checkout and the machine, and ends with one line. Paste its whole output into any bug report. On macOS with Colima, a folder outside the ones Colima shares mounts empty, and the doctor's checkout line says so.

## The interface

`segasms.Machine(model=None, cartridge=None, bios=None, region=None, handheld_mode=True)` builds a console. `cartridge` and `bios` are boards built with `smsmapper.Cartridge` from the bytes of a dump, and either may be left out. With a BIOS the console starts in it, as the hardware does, and the BIOS finds and starts the cartridge; without one it starts the cartridge at 0000h. `handheld_mode=False` puts a Game Gear in Master System mode, as a cartridge that grounds pin 42 does: ports 0 to 6 disappear, START becomes pause and the whole 256 by 192 picture is shown.

| Model      | Aliases                                  | VDP        | Processor | Region left out |
| :--------- | :--------------------------------------- | :--------- | :-------- | :-------------- |
| `mark-iii` | `mark3`, `markiii`, `sg-1000 mark iii`   | `315-5124` | `z80`     | `japan`         |
| `sms`      | `master system`, `sms1`, `master-system` | `315-5124` | `z80`     | `usa`           |
| `sms2`     | `master system ii`, `master-system-ii`   | `315-5246` | `z80`     | `usa`           |
| `gg`       | `game gear`, `game-gear`, `gamegear`     | `315-5378` | `z80`     | `usa`           |

Every alias `smsmapper` accepts for a console works here too. `region` is `japan`, `usa` or `europe`; a European Master System runs its VDP at 313 lines a frame, and every other console at 262.

```python
import segasms

for machine in (
    segasms.Machine("mark-iii"),
    segasms.Machine("sms", region="europe"),
    segasms.Machine("sms2"),
    segasms.Machine("gg"),
):
    print(machine.console.model.name, machine.console.region, machine.vdp.model, machine.vdp.region)
```

```
mark-iii japan 315-5124 ntsc
sms europe 315-5124 pal
sms2 usa 315-5246 ntsc
gg usa 315-5378 ntsc
```

### Calls

| Call                        | Effect                                                                                                   |
| :-------------------------- | :------------------------------------------------------------------------------------------------------- |
| `reset()`                   | Resets the VDP and the processor, as the reset line does. Returns the machine                            |
| `step()`                    | Runs one instruction, with the VDP moving three ticks for each of its T states                           |
| `run_frame(limit=100000)`   | Runs until the VDP finishes a frame and returns it; `NoFrame` after `limit` instructions                 |
| `press(button, player=1)`   | Holds a controller button, or `pause` or `start`                                                         |
| `release(button, player=1)` | Lets it go                                                                                               |
| `windowed()`                | True when a frame is shown through the Game Gear's 160 by 144 window, which happens only in its own mode |

### State

| Attribute | Meaning                                                                         |
| :-------- | :------------------------------------------------------------------------------ |
| `cpu`     | The `z80.Cpu`: `registers`, `cycles`, `irq_line`, `nmi_line`                    |
| `vdp`     | The `segavdp` part: `line`, `dot`, `registers`, `cram`, `sound`, `cycles`       |
| `console` | The `smsmapper.Console`: the memory map, the slot enables, the controller ports |

A `Frame` holds `colours`, the colour RAM word of every active dot, `width` and `height`, and `digest()`.

### Module contents

| Name                         | Content                                                       |
| :--------------------------- | :------------------------------------------------------------ |
| `segasms.Machine`            | One console                                                   |
| `segasms.Frame`              | One finished frame                                            |
| `segasms.MODELS`             | The four `Model` records, keyed by console name               |
| `segasms.Model`              | A console's name, its VDP part and its processor              |
| `segasms.NoFrame`            | Raised when no frame finishes within the instructions allowed |
| `segasms.UnknownModelError`  | Raised for a console name `smsmapper` does not have           |
| `segasms.UnknownRegionError` | Raised for a region other than `japan`, `usa` and `europe`    |
| `segasms.__version__`        | The installed version                                         |

```python
import segasms

for name, model in sorted(segasms.MODELS.items()):
    print(name, model.vdp, model.processor)

try:
    segasms.Machine("neo geo")
except segasms.UnknownModelError as error:
    print(error)
```

```
gg 315-5378 z80
mark-iii 315-5124 z80
sms 315-5124 z80
sms2 315-5246 z80
no console is called 'neo geo'; the consoles are ['gg', 'mark-iii', 'sms', 'sms2']
```

### Modules

| Module            | Holds                                                                               |
| :---------------- | :---------------------------------------------------------------------------------- |
| `segasms.machine` | The console: the three parts on one clock                                           |
| `segasms.bus`     | The processor's memory and ports, routed to the board and the VDP                   |
| `segasms.frame`   | A finished frame, and the screen that collects one dot by dot                       |
| `segasms.models`  | Each console's VDP part and processor, and which VDP region a console's region runs |
| `segasms.errors`  | Everything the package raises of its own                                            |
| `segasms.speaker` | The sound generator's output, averaged into 44,100 Hz stereo samples                |
| `segasms.record`  | The recorder: an animated PNG and a WAV from any image                              |
| `window.play`     | The window: picture, sound and the keyboard as the pad                              |

## The clock

The VDP's `tick()` is a third of a processor clock, and the processor calls the board once at the end of every T state. The board moves the VDP three ticks there, then copies the VDP's interrupt pin to the processor's maskable line and the pause button, or the Game Gear's start in Master System mode, to its non-maskable one. A port access lands where the processor's strobe does, 10 ticks into its I/O cycle: three T states and the first tick of the fourth. The VDP takes a write there, the processor takes a read there, and the interrupt pin each earlier T state saw is the one the processor samples. Nothing on the board reads the crystal itself, so the VDP tick, a fifth of the crystal on every model, is the finest step there is.

```python
import smsmapper
import segasms

program = bytes([0xED, 0x56, 0x3E, 0x20, 0xD3, 0xBF, 0x3E, 0x81, 0xD3, 0xBF, 0xFB, 0x18, 0xFE])
cartridge = smsmapper.Cartridge(program + bytes(0x8000 - len(program)))
machine = segasms.Machine("sms", cartridge=cartridge).reset()
machine.cpu.registers.sp = 0xDFF0

before = (machine.cpu.cycles, machine.vdp.cycles)
machine.cpu.run_until(lambda part: part.registers.pc == 0x0038, limit=20000)
states = machine.cpu.cycles - before[0]
ticks = machine.vdp.cycles - before[1]
print(states, ticks, ticks == 3 * states, machine.vdp.line, hex(machine.vdp.status))
```

```
43969 131907 True 193 0x80
```

The program sets interrupt mode 1, enables the frame interrupt in register 1 and waits. When the VDP raises its frame flag, the processor finishes the `jr` it is in and restarts at 0038h: 43,969 T states from the reset, and exactly three VDP ticks for each.

A port reaches what the console's decode names. The VDP's data, control and counter ports and the sound generator go to the VDP package, everything else to the board. A write to port 3F that raises TH as an output latches the VDP's H counter in the same T state, and on a Game Gear a write to port 6 also sets the sound generator's stereo register.

```python
import smsmapper
import segasms

program = bytes([0x3E, 0x0F, 0xD3, 0x06, 0x18, 0xFE])
game_gear = segasms.Machine("gg", cartridge=smsmapper.Cartridge(program + bytes(0x7FFA))).reset()
game_gear.step()
game_gear.step()
print(hex(game_gear.vdp.sound.stereo), hex(game_gear.console.registers[6]))

console = segasms.Machine(
    "sms", cartridge=smsmapper.Cartridge(bytes([0x18, 0xFE]) + bytes(0x7FFE))
).reset()
console.cpu.registers.sp = 0xDFF0
console.press("pause")
taken = [console.step() and console.cpu.registers.pc for _ in range(4)]
print([hex(one) for one in taken])
```

```
0xf 0xf
['0x66', '0x67', '0x68', '0x69']
```

The Game Gear's write to port 6 lands in the board's register and in the stereo register alike. Holding pause takes the non-maskable interrupt at 0066h once, however long it is held, and the processor runs on from there.

## Booting the BIOS

A BIOS image is a board like any cartridge. Built with `bios=smsmapper.Cartridge(image)`, the console starts in it with the cartridge slot off, and the BIOS draws its logo, copies its loader to RAM at C700h, turns the cartridge on through port 3E and checks it before starting it. On a Master System with BIOS 1.3 and _Sonic The Hedgehog_, the logo is up by frame 120, port 3E turns the cartridge on near frame 340, and Sonic draws from about frame 650.

## Playing and recording

```bash
scripts/play "Sonic The Hedgehog.sms"
scripts/play "Sonic The Hedgehog.sms" --replay 300
scripts/run python -m segasms.record "Sonic The Hedgehog.sms" --frames 300 --out recordings
```

`scripts/play` opens a window and runs the same machine the tests run, at the speed the cycle-by-cycle model reaches, a few frames a second. Nothing is traded for speed. The arrows are the pad, Z and X are buttons 1 and 2, Return is pause, or start on a Game Gear, Backspace is the Master System's reset button, and Escape or closing the window stops. Each frame's sound plays as the frame finishes, at its true pitch, with silence until the next one. `--replay N` emulates N frames first, then plays picture and sound together at the console's speed. `--bios FILE` boots an original BIOS first; without one, a Master System starts where the BIOS hands over and a Game Gear from its reset values. `--scale N` sets the window size, 3 by default. `--mode master-system` runs the image on a Game Gear in Master System mode, for a Game Gear cartridge that grounds pin 42, such as R.C. Grand Prix (USA). The window never opens full screen.

The window is the one tool that runs on the host rather than in the image, because a container has no display or sound device. It needs uv, which brings Python 3.12.14 and the pygame-ce that `uv.lock` pins into a cache folder outside the checkout. On Windows, run `scripts\play.ps1`.

`segasms.record` runs in the image and writes `<name>.png`, an animated PNG showing each frame for the time it took on the console, and `<name>.wav`, 16-bit stereo at 44,100 Hz. Each sample is the sound generator's output averaged over the periods it spans. Seconds come from the 3.58 MHz the Mark III manual prints for the processor, used on every model. A Game Gear frame is its 160 by 144 window, and in Master System mode, which `--mode master-system` selects here too, the whole 256 by 192 picture. A browser plays the PNG.

## The census

```bash
scripts/run python -m conformance.census "external/Master EverDrive" "external/EverDrive GG" --frames 300 --jobs 2
```

The census boots every image in a Master System and Game Gear library from its cartridge, on the board MAME's software lists name for it, and runs it for the frame bound. A `.sms` image runs on a Master System and a `.gg` image on a Game Gear, except a Game Gear cartridge that MAME's list marks as grounding pin 42, which runs on a Game Gear in Master System mode; an image that only the European set lists runs on a European console. For each distinct image it keeps the first frame that shows more than one colour and SHA-256 chained over every frame's digest, so a later run tells at once whether any dot of any frame moved. It accepts directories, zip archives and single images, prints a summary, writes [`conformance/corpus.json`](conformance/corpus.json), and exits 1 when a property breaks.

Two properties gate the run: the machine raises no exception on any image, and every retail image draws more than one colour within the frame bound. A retail cartridge that never draws is a console this package has wrong. An image other than a retail one that never draws, such as a beta or a demo, is counted and named rather than failed.

| Result of the last run                        | Count |
| :-------------------------------------------- | :---- |
| Listings across both libraries                | 5,110 |
| Distinct images                               | 2,608 |
| Retail images, the ones that gate             | 813   |
| Run on a European console, 313 lines a frame  | 233   |
| Drew more than one colour in the first second | 2,014 |
| Drew more than one colour later               | 545   |
| Never drew more than one colour               | 49    |

[`conformance/corpus.json`](conformance/corpus.json) holds those counts, the first drawn frame and the chained digest of each image by its SHA-256, and nothing from any cartridge.

## Is it right

The parts are held to their own members: the Z80 to SingleStepTests and its census, the VDP package to Sega's manual, the TI documents and its census, the board to the manual and its census. This repository holds what joining them adds: which line drives which pin, the three ticks to a T state, and the boot path. [`conformance/hardware.json`](conformance/hardware.json) carries each of those facts with its source, and every value no document prints sits under `notStated`, marked unverified, with the measurement that would settle it. [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) lists them.

## Working on it

| Need                                                            | Where                                                               |
| :-------------------------------------------------------------- | :------------------------------------------------------------------ |
| Every gate and the order to run them                            | [CONTRIBUTING.md](CONTRIBUTING.md)                                  |
| The same material for a coding agent                            | [AGENTS.md](AGENTS.md)                                              |
| The standard this repository shares with the rest of the family | [FAMILY.md](FAMILY.md)                                              |
| Bug reports                                                     | [GitHub Issues](https://github.com/gufranco/sega-sms-python/issues) |
| Security reports                                                | [SECURITY.md](SECURITY.md)                                          |

```bash
scripts/run make gate
scripts/run python segasms/machine.test.py
```

`make gate` runs the formatters, the linter, the type checker, the YAML checker and every test under coverage, which is a hard gate at 100% statement and branch with nothing excluded. Each module has a test file beside it, named after it, and each runs on its own as above.

## References

- _Software Reference Manual for the SEGA Mark III Console_, Sega, undated, a retyped copy. 45 pages, 184,840 bytes, SHA-256 `166f09331ba9df055f7a352f10c6a7843911470bc72d9347eda4a0de86e8cfce`. It is not redistributable and is not in this repository. `scripts/run python -m conformance.documents` downloads it from https://segaretro.org/images/d/d6/SoftwareReferenceManualForSegaMarkIIIEU.pdf and refuses any other file.
- MAME, `hash/sms.xml` and `hash/gamegear.xml` at commit `94fc55c9692b180dcb608e2e222e48315db5017a`, https://github.com/mamedev/mame, through `sms-mapper-python`, for the board each image is on.

## Citing this

[CITATION.cff](CITATION.cff) is updated with each release by the script that stamps the package version.

## License

MIT. See [LICENSE](LICENSE).
