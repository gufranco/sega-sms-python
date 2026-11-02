import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FILE = json.loads((ROOT / "conformance" / "documents.json").read_text())["documents"][0]["file"]

HELD = ROOT / "docs" / FILE


def flatten(laid_out: str) -> str:
    return re.sub(r"[^a-z0-9]", "", laid_out.lower())


def text(pdf: Path = HELD) -> str:
    if not pdf.is_file() or shutil.which("pdftotext") is None:
        return ""
    done = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True, check=True
    )
    return flatten(done.stdout)
