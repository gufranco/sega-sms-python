## What this changes

One or two sentences. What is different afterwards, and why it needed to be.

## How it was checked

Paste the output rather than describing it. A claim that the tests pass is not
evidence that they did.

```text

```

- [ ] `ruff format --check .` and `ruff check .` are clean
- [ ] `mypy` reports nothing
- [ ] Every test file runs, and coverage is 100% of statements and branches
- [ ] Every new check was run once against input that should fail it

## If this changes a board, the memory map or a port

The tests alone do not check a change here. Run the census over a Master System and
Game Gear library you own and paste what it prints:

```text
  ok    the model raises on no image: 0 broken
  ok    every retail image over 48K writes a register of its board within the frame bound: 0 broken
  observed  images that select a bank past the end of the image: N images
```

Deduplicate by digest before quoting a count. A library organised by series
lists the same image several times.

## What it does not carry

- [ ] No cartridge, no fragment of one, and no digest fine enough to rebuild one
- [ ] Nothing that says where to obtain them
