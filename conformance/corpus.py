import collections
import json
import sys
from pathlib import Path
from typing import Any

CORPUS = Path(__file__).resolve().parent / "corpus.json"

COUNTS = ("gated", "pal")


def broken(held: dict[str, Any]) -> list[str]:
    return [name for name, count in held["properties"].items() if count]


def inconsistent(held: dict[str, Any]) -> list[str]:
    images = held["images"]
    frames = held["frames"]
    drew = {int(frame): count for frame, count in held["drew"].items()}
    runs = held["runs"]
    from_runs = collections.Counter(first for first, _ in runs.values() if first is not None)
    problems = []
    if len(runs) != images:
        problems.append(f"{len(runs)} runs for {images} images")
    if sum(drew.values()) > images:
        problems.append(f"{sum(drew.values())} images drew of {images}")
    problems += [
        f"an image drew first at frame {frame} of {frames}" for frame in drew if frame >= frames
    ]
    problems += [
        f"{name} is {held[name]} of {images} images" for name in COUNTS if held[name] > images
    ]
    if dict(from_runs) != drew:
        problems.append("the runs' first drawn frames do not add up to the tally")
    return problems


def main(where: Path = CORPUS) -> int:
    held = json.loads(where.read_text())
    print(
        f"{held['images']} images, {held['gated']} retail, {held['frames']} frames each,"
        f" {sum(held['drew'].values())} drew"
    )
    for name, count in held["properties"].items():
        print(f"  {'ok  ' if not count else '   !'}  {name}: {count} broken")
    problems = inconsistent(held)
    for problem in problems:
        print(f"     !  {problem}")
    return 1 if broken(held) or problems else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else CORPUS))
