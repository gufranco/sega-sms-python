# Working in this repository

Read [FAMILY.md](FAMILY.md) first. It is the standard every member of this
family carries, byte for byte, and it decides most questions before they are
asked. What follows is only what is true of this member. [README.md](README.md)
is the document written for a person.

## What this project is, in one paragraph

A model of the Sega Mark III, both Master Systems and the Game Gear as one
machine: the Z80 from `zilog-z80-python`, the VDP package with its sound
generator from `sega-vdp-python`, and the board from `sms-mapper-python`, on one
clock. It loads an original BIOS, boots a real cartridge and gives the frame
the VDP drew, dot by dot. Each part is held to its own member; this one holds
only the joining: which line drives which pin, the three VDP ticks to a T
state, the port routing and the boot path. What the manual prints about those
comes from Sega's Mark III reference manual, and whether every retail cartridge
boots and draws comes from a census over the Master System and Game Gear
libraries.

## The interface a caller drives

- `segasms.Machine(model, cartridge=..., bios=..., region=...,
handheld_mode=...)` builds a console. `model` is any name or alias
  `smsmapper` accepts; the cartridge and the BIOS are `smsmapper.Cartridge`
  boards. `handheld_mode=False` puts a Game Gear in Master System mode, and
  `windowed()` says whether a frame is cropped to the 160 by 144 window.
- `reset`, `step`, `run_frame`, `press` and `release` drive it. `cpu`, `vdp`
  and `console` are the three parts, for reading their state.
- `segasms.Frame` is one finished frame: the colour RAM word of every active
  dot, its width and height, and `digest()`.
- `handed_over()` puts a Master System where the BIOS leaves it, for a run
  without a BIOS; a Game Gear keeps its reset values.
- `machine.speaker.take()` gives the sound since the last take, 16-bit stereo
  at 44,100 Hz, interleaved left then right.
- `segasms.record` and `window.play` are the two tools on top: the recorder
  runs in the image, the window on the host through `scripts/play`.

Everything the package raises lives in
[`segasms/errors.py`](segasms/errors.py), apart from the two console errors it
passes on from `smsmapper`.

The processor drives time. `z80`'s `on_cycle` runs once at the end of every T
state, and [`segasms/machine.py`](segasms/machine.py) moves the VDP three ticks
there, then copies the VDP's INT pin to `irq_line` and the board's NMI to
`nmi_line`.

A port access does not land when `z80` calls the port: that happens at the
start of the I/O cycle, before IORQ is active. `Machine.strobe` first runs the
VDP 10 ticks ahead to the falling edge of T3, where the processor samples a
read and the VDP latches a write, and keeps the INT pin of each T state it
passed so the processor still samples the pin its own state saw. The next
`on_cycle` calls owe only the ticks left over.

## The authority ladder

1. **[`conformance/hardware.json`](conformance/hardware.json) facts**, quoted
   from Sega's Mark III reference manual and matched against its text layer by
   [`conformance/quotes.py`](conformance/quotes.py).
2. **The original BIOS images run on this package**, for the state a console
   is in when the BIOS starts a cartridge, under `notStated` with
   `verified: false`.
3. **The cartridge libraries**, through
   [`conformance/census.py`](conformance/census.py), for whether every retail
   cartridge boots and draws.

## What is settled and what is not

**Settled: everything the manual prints about the joining and a test can
reach.** Each fact in [`conformance/hardware.json`](conformance/hardware.json)
names, under `heldBy`, the test in
[`conformance/hardware.test.py`](conformance/hardware.test.py) that holds it.
The processor's clock in megahertz is held through the sound: a second of
samples is 3.58 million T states.

**Not settled: 4 things**, each in [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) with
what would close it. Do not close one by argument.

## A frame is sampled when a dot completes

`segavdp`'s `line` and `dot` move to the next dot halfway through it, while
`shown` and `colour` still describe the dot just drawn. Sampled after every
tick, they pair one dot's position with the last one's colour, and a frame
comes out one dot long. [`segasms/frame.py`](segasms/frame.py) samples only on
the second tick of each dot, counted from the reset, and closes a frame when
the beam returns to line 0, dot 0.

## Files kept in `external/`

Everything this member reads and may not ship sits in `external/`, which git
ignores and Dropbox is told to leave alone, per FAMILY.md's "Where the files a
member reads are kept". [`artifacts.manifest.json`](artifacts.manifest.json)
names every file by size, CRC32, MD5, SHA-1 and SHA-256:

- `external/Master EverDrive/`, the archives of the Master EverDrive pack of
  2022-05-04, which the census walks whole. One of them,
  `5 Tools & Service Test Carts.zip`, holds the BIOS images.
- `external/EverDrive GG/`, the archives of the EverDrive GG pack of
  2020-12-21, which the census walks whole.

```bash
scripts/run python -m conformance.external
scripts/run python -m conformance.external --describe external/<file>
```

## The census starts where the BIOS hands over

A census run boots the cartridge itself, without a BIOS, because a BIOS boot
costs 350 to 650 frames before the cartridge starts. A Master System run
starts as the BIOS leaves the console: the stack at DFF0h and RAM C000h holding
ABh, measured by running BIOS 1.3 and 2.0 on this package. A Game Gear run
starts from its reset values. `Machine.handed_over()` holds that state, and the
census, the test cartridges, the recorder and the window all start from it.

A Game Gear cartridge that grounds pin 42 runs on a Game Gear in Master System
mode, whatever its file is called. The census and the comparison read that
list, `smsMode` in `sms-mapper-python`'s `conformance/boards.json`, taken from
MAME's Game Gear list. R.C. Grand Prix (USA) is the one a Master System cannot
start: it writes FFh to port 02h, which a Master System's decode sends to the
memory control register, and the cartridge switches itself off. The recorder
and the window take `--mode master-system` for it.

## Every gate, in the order to run them

```bash
scripts/run make gate
```

`make gate` runs, in order, `ruff format --check`, `prettier --check`,
`ruff check`, `mypy`, `yamllint --strict` and every test under coverage, at
the versions `uv.lock` and `pnpm-lock.yaml` pin inside the image. Then the
ones outside the coverage step:

```bash
scripts/run python -m conformance.corpus
scripts/run python -m conformance.speed
```

And, with the manual and the libraries present:

```bash
scripts/run make conformance
scripts/run python -m conformance.census "external/Master EverDrive" "external/EverDrive GG" --frames 300 --jobs 2
```

Everything under [`conformance/`](conformance) runs as a module. Run as a
script, its own directory goes on the import path and a file there shadows any
standard library module of the same name.

## Conventions that are not negotiable

| Thing        | Rule                                                                                                                                              |
| :----------- | :------------------------------------------------------------------------------------------------------------------------------------------------ |
| Language     | Python only, run in the image                                                                                                                     |
| Dependencies | Docker and git on the host, plus uv for the window alone; everything else pinned in the image                                                     |
| Comments     | None in source or in build files, and a docstring counts as one. Names, small functions, constants and types carry what a comment would have said |
| Test layout  | `<module>.test.py` beside the module it covers                                                                                                    |
| Test shape   | Arrange, act, assert, each opened by its bare marker                                                                                              |
| Coverage     | 100% statements and branches, enforced, with no exclusion of any kind                                                                             |
| Types        | `mypy` at strict, plus every optional error class                                                                                                 |
| Tooling      | uv for Python and pnpm for JavaScript, never pip or npm                                                                                           |
| Commits      | Conventional Commits, subject at most 50 characters                                                                                               |
| Documents    | Read, quoted and pinned by digest. Never committed                                                                                                |
| Cartridges   | Never committed, in any form, for any reason                                                                                                      |

The linter's ignores in [`pyproject.toml`](pyproject.toml) carry no comments, so
their reasons live here:

- `N818`: some exceptions are signals rather than failures. The standard
  library names those without the suffix too.
- `N999` and `PLR2004` in tests: a test file is named after its module with a
  dot, and its literals are the expected values.
- `T201` in `conformance/`, the doctor and `environment.py`: printing is their
  output.
- `BLE001` in the doctor, `environment.py` and the census: a check that throws
  has to become a line in the report rather than end the run. One image that
  raises must not throw away the census's results for every other image.
- The `z80.*` override: the processor is typed and checked in its own
  repository against its own gate.
- The three submodules and `external/` in the linter's and coverage's
  exclusions: they are other members' code and other projects' files, each
  checked in its own repository.

## Layout

```
segasms/
  machine.py      the console: the three parts on one clock
  bus.py          the processor's memory and ports, routed to the board and the VDP
  frame.py        a finished frame, the screen that collects one dot by dot, and the Game Gear window
  speaker.py      the sound generator's output as 44,100 Hz stereo samples
  record.py       the recorder: an animated PNG and a WAV
  models.py       each console's VDP part and processor
  errors.py       everything this package raises
  doctor.py       what the container and the package look like, for a report
  environment.py  what the doctor reads about the container
  version.py      rewritten by the release job and by nothing else
conformance/
  census.py         boots every image in a library you own and records its frames
  corpus.json       the census counts and each image's digests, nothing from any cartridge
  corpus.py         replays them
  hardware.json     Sega's manual on the joining, fact by fact, and every value it does not print
  divergences.json  every place two sources part
  bench.py          the record, loaded once
  documents.json    the manual, by digest
  documents.py      brings it down and refuses any other file
  external.py       which of the files in external/ are here, verified, missing or wrong
  manual.py         the manual's text, flattened to letters and digits
  quotes.py         every quote the record carries, found in the manual
  links.py          the weekly check that every cited address still answers
  speed.py          the throughput floor
  source.py         the check that no documentation string remains
  family_*.test.py  the family standard, held as tests, one topic a file
  family_member.py  what this member answers to them
  family_shared.py  what more than one of them reads
window/
  play.py         the window: picture, sound and the keyboard as the pad, outside the package
zilog-z80-python/   the processor, a pinned submodule
sega-vdp-python/    the VDP package, a pinned submodule carrying the TI members
sms-mapper-python/  the board, a pinned submodule
scripts/run         runs any command in the image, with the checkout mounted
scripts/play        opens the window on the host, through uv
Dockerfile          the image: Python, uv, Node and every tool, pinned
Makefile            the gate, target by target
external/           the libraries, never committed
artifacts.manifest.json  every file in external/, by digest
```

## Things that will bite you

**The VDP powers on scrambled.** Build a `segavdp.Chip` without resetting it
and its registers and its half-written command are whatever the seed gave
them. `Machine.reset()` resets it; a test that builds a part on its own resets
it too.

**Mode 4 needs register 0 bit 2.** A program that sets the backdrop or the line
interrupt without it runs the part in its legacy mode, where the backdrop
comes from the fixed colour table and the line counter does not run.

**The line counter starts after its first reload.** From a reset the first
line interrupt comes only after the first blanking, a few thousand
instructions in.

**The image's VM may be small.** On macOS with Colima, `docker info` shows the
CPUs a census gets, and other containers share them.

## Before calling anything finished

[`FAMILY.md`](FAMILY.md) carries a checklist under "What a new repository has to
have before it is a member". Every line on it was a defect found in one of these
repositories and fixed in all of them. Read it before adding a surface, and read
it again before saying a change is done.

**A check nobody has seen fail is not known to work.** Drive it, once,
deliberately, against input that should fail it.

**Silence and success produce the same output.** A census that walked no file
says so, and exits non-zero.

## What a change is expected to leave behind

A gate that would have caught the bug. A change to the clock, the routing or
the boot path also runs the census over a real library: the tests check what
the manual says, and the census checks that every retail cartridge still
boots and draws.
