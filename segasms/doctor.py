from __future__ import annotations

import hashlib
import importlib
import json
import platform
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Protocol, cast, override


def installed_version(where: Path | None = None) -> str:
    found = re.search(
        r"""VERSION\s*[:=][^"']*["']([^"']+)["']""",
        (where or Path(__file__).resolve().parent / "version.py").read_text(),
    )
    return found.group(1) if found else "unknown"


VERSION = installed_version()

ROOT = Path(__file__).resolve().parent.parent


def reachable(root: Path = ROOT, path: list[str] | None = None) -> bool:
    where = sys.path if path is None else path
    if str(root) in where:
        return False
    where.insert(0, str(root))
    return True


reachable()

CORPUS = ROOT / "conformance" / "corpus.json"

DOCUMENTS = ROOT / "conformance" / "documents.json"

HELD_DOCUMENTS = ROOT / "docs"

OLDEST_PYTHON = (3, 12)

PACKAGE = "segasms"

MEMBERS = {
    "z80": "zilog-z80-python",
    "segavdp": "sega-vdp-python",
    "smsmapper": "sms-mapper-python",
}

VISIBLE = (
    "FAMILY.md",
    "zilog-z80-python/FAMILY.md",
    "sega-vdp-python/FAMILY.md",
    "sms-mapper-python/FAMILY.md",
)

MODEL = "sms"

TICKS_PER_T_STATE = 3

ACTIVE_DOTS = 256 * 192

BLANK_CARTRIDGE = bytes([0x18, 0xFE]) + bytes(0x8000 - 2)

CHECKS = (
    "python",
    "package",
    "members",
    "checkout",
    "clock",
    "frame",
    "manual",
    "corpus",
    "library",
)


class Finding:
    __slots__ = ("advice", "detail", "name", "ok")

    def __init__(self, name: str, ok: bool, detail: str, advice: str | None = None) -> None:
        self.name = name
        self.ok = ok
        self.detail = detail
        self.advice = advice

    @property
    def line(self) -> str:
        return f"  {'ok  ' if self.ok else '   !'}  {self.name}: {self.detail}"

    @property
    def report(self) -> str:
        if self.ok or not self.advice:
            return self.line
        return f"{self.line}\n         {self.advice}"

    @override
    def __repr__(self) -> str:
        return f"<Finding {self.name} {'ok' if self.ok else 'not ok'}>"


def _threw(name: str, error: BaseException, advice: str | None = None) -> Finding:
    return Finding(name, False, f"{type(error).__name__}: {error}", advice)


def check_python(oldest: tuple[int, int] = OLDEST_PYTHON) -> Finding:
    return Finding(
        "python",
        sys.version_info[:2] >= oldest,
        platform.python_version(),
        f"this package needs {oldest[0]}.{oldest[1]} or newer; rebuild the image with scripts/run",
    )


def check_package(name: str = PACKAGE) -> Finding:
    try:
        loaded = importlib.import_module(name)
    except ImportError as error:
        return _threw("package", error, "the package did not import from the checkout")
    return Finding("package", True, f"{name} {loaded.__version__} imported from {ROOT}")


def check_members(members: Mapping[str, str] = MEMBERS) -> Finding:
    found: list[str] = []
    missing: list[str] = []
    for module, folder in members.items():
        try:
            found.append(f"{module} {importlib.import_module(module).__version__}")
        except ImportError:
            missing.append(folder)
    if missing:
        return Finding(
            "members",
            False,
            f"not importable: {', '.join(missing)}",
            "run git submodule update --init --recursive in the checkout, then scripts/run again",
        )
    return Finding("members", True, ", ".join(found))


def check_checkout(root: Path = ROOT, visible: Sequence[str] = VISIBLE) -> Finding:
    missing = [one for one in visible if not (root / one).is_file()]
    if missing:
        return Finding(
            "checkout",
            False,
            f"not visible in {root}: {', '.join(missing)}",
            "clone with --recurse-submodules into a folder Docker shares; on macOS with Colima, "
            "a folder outside the shared ones mounts empty",
        )
    return Finding("checkout", True, f"{root} holds the checkout and its three members")


class Counted(Protocol):
    cycles: int


class Picture(Protocol):
    colours: tuple[int, ...]


class Running(Protocol):
    cpu: Counted
    vdp: Counted
    step: Callable[[], int]
    run_frame: Callable[[], Picture]


def _machine(model: str) -> Running:
    package = importlib.import_module(PACKAGE)
    cartridge = importlib.import_module("smsmapper").Cartridge(BLANK_CARTRIDGE)
    return cast("Running", package.Machine(model, cartridge=cartridge).reset())


def check_clock(model: str = MODEL, expected: int = TICKS_PER_T_STATE) -> Finding:
    try:
        machine = _machine(model)
        before = (machine.cpu.cycles, machine.vdp.cycles)
        machine.step()
        states = machine.cpu.cycles - before[0]
        ticks = machine.vdp.cycles - before[1]
    except Exception as error:
        return _threw("clock", error)
    return Finding(
        "clock",
        ticks == expected * states,
        f"{states} T states moved the VDP {ticks} ticks",
        f"the VDP must move {expected} ticks for every T state",
    )


def check_frame(model: str = MODEL, expected: int = ACTIVE_DOTS) -> Finding:
    try:
        shown = len(_machine(model).run_frame().colours)
    except Exception as error:
        return _threw("frame", error)
    return Finding(
        "frame",
        shown == expected,
        f"a frame held {shown} active dots",
        f"a frame holds {expected} active dots, 256 by 192",
    )


def check_manual(manifest: Path = DOCUMENTS, held: Path = HELD_DOCUMENTS) -> Finding:
    try:
        entry = json.loads(manifest.read_text())["documents"][0]
        where = held / str(entry["file"])
        if not where.is_file():
            return Finding(
                "manual",
                True,
                f"not here: {where}; the quote check will report checking none",
                None,
            )
        agrees = hashlib.sha256(where.read_bytes()).hexdigest() == entry["sha256"]
    except Exception as error:
        return _threw("manual", error)
    return Finding(
        "manual",
        agrees,
        f"{where.name} is the pinned scan" if agrees else f"{where.name} is a different file",
        "fetch it again with scripts/run python -m conformance.documents",
    )


def check_corpus(path: Path | str = CORPUS) -> Finding:
    where = Path(path)
    if not where.is_file():
        return Finding("corpus", False, f"not here: {where}", "run the census to build one")
    try:
        examined = int(json.loads(where.read_text())["images"])
    except Exception as error:
        return _threw("corpus", error, f"{where} did not parse")
    return Finding(
        "corpus",
        examined > 0,
        f"{examined} images behind it",
        "a census that examined no image writes an empty corpus, so check what it walked",
    )


def check_library() -> Finding:
    return Finding(
        "library",
        True,
        "the census takes the library to walk as an argument, so there is nothing to be set wrongly",
    )


def examine(corpus: Path | str = CORPUS) -> list[Finding]:
    return [
        check_python(),
        check_package(),
        check_members(),
        check_checkout(),
        check_clock(),
        check_frame(),
        check_manual(),
        check_corpus(corpus),
        check_library(),
    ]


def report(found: Sequence[Finding]) -> list[str]:
    from segasms import environment

    unwell = [one for one in found if not one.ok]
    lines = [
        f"segasms {VERSION} on {platform.python_version()}, {platform.system()}",
        "",
        "  the container",
        *environment.lines(ROOT),
        "",
        "  this package",
        *(one.report for one in found),
        "",
    ]
    if unwell:
        lines.append(f"  {len(unwell)} of {len(found)} checks did not pass")
    else:
        lines.append(f"  {len(found)} checks, nothing to report")
    return lines


def main(
    argv: Sequence[str] = (),
    examine: Callable[..., list[Finding]] = examine,
    say: Callable[[str], None] = print,
) -> int:
    found = examine()
    for line in report(found):
        say(line)
    return 1 if any(not one.ok for one in found) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
