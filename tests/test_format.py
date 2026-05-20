from typing import TYPE_CHECKING

from openapi_pyx.codegen.format import format_directory

if TYPE_CHECKING:
    from pathlib import Path


def test_format_normalizes_quotes_and_spacing(tmp_path: Path) -> None:
    (tmp_path / "x.py").write_text("x=1\ny = 'a'\n")
    format_directory(tmp_path)
    out = (tmp_path / "x.py").read_text()
    assert "x = 1" in out
    assert '"a"' in out


def test_format_sorts_imports(tmp_path: Path) -> None:
    (tmp_path / "x.py").write_text("import sys\nimport os\nprint(os, sys)\n")
    format_directory(tmp_path)
    out = (tmp_path / "x.py").read_text()
    os_idx = out.index("import os")
    sys_idx = out.index("import sys")
    assert os_idx < sys_idx
