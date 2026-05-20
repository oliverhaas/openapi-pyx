"""Run `ruff` against a directory of emitted Python files."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path


def format_directory(directory: Path) -> None:
    """Run `ruff format` and `ruff check --fix --select I,F401` over `directory`."""
    if not directory.exists():
        raise FileNotFoundError(directory)
    _run([sys.executable, "-m", "ruff", "format", "--isolated", str(directory)])
    _run([sys.executable, "-m", "ruff", "check", "--isolated", "--fix", "--select", "I,F401", str(directory)])


def _run(args: list[str]) -> None:
    result = subprocess.run(args, check=False, capture_output=True, text=True)  # noqa: S603
    if result.returncode != 0:
        raise RuntimeError(
            f"`{' '.join(args)}` failed (rc={result.returncode}):\n{result.stdout}\n{result.stderr}",
        )
