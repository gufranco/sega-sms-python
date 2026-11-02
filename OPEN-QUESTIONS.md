# Open questions

What this project does not know for certain about how the machine is joined, and what it would take to find out.

Each part is held to its own member, so its open questions live there: the processor's in `zilog-z80-python`, the VDP package's in `sega-vdp-python`, the board's in `sms-mapper-python`. What sits here is only what joining them adds. The only Sega document is the Mark III reference manual, which says which pin the pause button drives and which events raise the maskable interrupt, and nothing about the later consoles.

Every entry is also in [`conformance/hardware.json`](conformance/hardware.json) under `notStated`, or in [`conformance/divergences.json`](conformance/divergences.json), so a program can read what a person reads here.

## What would settle almost all of them

A Master System of each revision and a Game Gear, each running a cartridge whose first instructions show the state they find on screen. A Game Gear with an EverDrive GG and a Japanese Master System are available; no export Master System or Master System II is.

## What the manual does not print

### What the BIOS leaves when it starts a cartridge

**This package does.** The census starts every Master System run with the stack at DFF0h and RAM C000h holding ABh.

**Why it is open.** No Sega document prints the state the BIOS hands over. The values come from running the original BIOS 1.3 and 2.0 on this package, so they are only as right as this package.

**Where the value came from.** BIOS 1.3 and BIOS 2.0 run on this package with Sonic The Hedgehog, read at the instruction at 0000h: SP DFF0h and C000h ABh, at frames 621 and 349.

**What would settle it.** On a Master System with each BIOS, start a cartridge whose first instructions write SP and the byte at C000h to the screen, and read them.

### Which Z80 the Master System II and the Game Gear carry

**This package does.** Every console runs `zilog-z80-python`'s NMOS `z80` model.

**Why it is open.** The manual names the Z80A for the Mark III only. The NMOS and CMOS parts differ in what OUT (C),0 sends and in the flag bits after SCF and CCF, and a game that reads either would tell them apart.

**Where the value came from.** The manual's processor section, read for the Mark III and assumed for the rest.

**What would settle it.** On each console run OUT (C),0 to a port whose written value can be read back, and SCF after an instruction that leaves the undocumented flag bits known, then compare with the `z80` and `z84c00` models.

### Where in an I/O cycle a port access lands

**This package does.** Every port access lands 10 master ticks into its I/O cycle: three whole T states and the first tick of the fourth. The interrupt pin the processor samples in the T states before that point is the one those states saw.

**Why it is open.** Zilog's manual holds IORQ with RD or WR from the rising edge of T2 to the falling edge of T3 and samples read data at that falling edge, and the TMS9918A data manual latches written data when CSW rises, so the access lands at the falling edge of T3. Neither says where that edge falls among the three master ticks of T3, which depends on the duty cycle of the processor clock the VDP divides out, nor how much of the VDP's access time comes before it. One tick either way moves a read across a counter step.

**Where the value came from.** Zilog Z80 CPU User Manual UM0080, input or output cycles, and the TMS9918A data manual of November 1982, CPU-VDP interface timing.

**What would settle it.** Software moves an access only by whole T states, three master ticks, so no sweep steps one tick. On a console that latches the H counter when TH changes, toggle TH through port 3Fh from instruction starts one T state apart across at least four starts, and read each latched value. Run the same cartridge here with the access at each of the three ticks of T3; the tick whose readings match the console's is the one.

## Where the sources part

### What RAM C000h holds when the BIOS starts a cartridge

**This package does.** Follows the BIOS run: ABh.

**Why it is open.** The census boards of `sms-mapper-python` and `sega-vdp-python` start a Master System run with A8h, a value no BIOS run on this package leaves. Bits 0 and 1 of port 3E select nothing, so a cartridge that masks them reads the two alike.

**What would settle it.** On a Master System with each BIOS, start a cartridge that shows the byte at C000h on screen.

## What is not in question

- The pause button drives the processor's non-maskable line, edge-triggered, and the VDP's two interrupt events drive its maskable one: the manual prints both, and [`conformance/hardware.test.py`](conformance/hardware.test.py) holds them.
- The VDP moves three ticks for each T state: `sega-vdp-python` defines its tick as a third of a processor clock, and the doctor checks the ratio on every run.

## What is deliberately not modelled

- The YM2413 FM unit of the Japanese Master System and the Mark III's FM adapter: a later member models it, and the board revision that carries it is wired in then.
- The light phaser, the 3-D glasses, the sports pad and the paddle.
- The SG-1000 and the SC-3000.
