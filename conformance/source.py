import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HOLDERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)

ASSIGNMENTS = (ast.Assign, ast.AnnAssign)


def _is_bare_string(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _documents_its_holder(body: list[ast.stmt], index: int) -> bool:
    opens_the_body = index == 0
    follows_an_assignment = index > 0 and isinstance(body[index - 1], ASSIGNMENTS)
    return _is_bare_string(body[index]) and (opens_the_body or follows_an_assignment)


def strings_in(path: Path) -> list[int]:
    tree = ast.parse(path.read_text())
    holders = [node for node in ast.walk(tree) if isinstance(node, HOLDERS)]
    return sorted(
        holder.body[index].lineno
        for holder in holders
        for index in range(len(holder.body))
        if _documents_its_holder(holder.body, index)
    )


def tracked_python(root: Path) -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=root, capture_output=True, text=True, check=True
    ).stdout.split()
    return [root / one for one in listed]


def offenders(root: Path) -> list[tuple[Path, list[int]]]:
    found = [(path, strings_in(path)) for path in tracked_python(root)]
    return [(path, lines) for path, lines in found if lines]


def report(found: list[tuple[Path, list[int]]], examined: int) -> int:
    for path, lines in found:
        for line in lines:
            print(f"{path}:{line}")
    if found:
        return 1
    print(f"{examined} files examined, none carries a documentation string")
    return 0


def main(argv: list[str]) -> int:
    root = Path(argv[0]) if argv else ROOT
    return report(offenders(root), len(tracked_python(root)))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
