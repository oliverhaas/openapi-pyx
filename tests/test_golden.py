import os
import shutil
from pathlib import Path

import pytest

from openapi_pyx.generate import generate_client

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = FIXTURES / "golden"

GOLDEN_CASES = [
    ("petstore", FIXTURES / "petstore.yaml"),
    ("primitives", FIXTURES / "edge" / "primitives.yaml"),
    ("nullable_array", FIXTURES / "edge" / "nullable_array.yaml"),
    ("allof_compose", FIXTURES / "edge" / "allof_compose.yaml"),
    ("oneof_discriminator", FIXTURES / "edge" / "oneof_discriminator.yaml"),
    ("oneof_no_discriminator", FIXTURES / "edge" / "oneof_no_discriminator.yaml"),
    ("anyof", FIXTURES / "edge" / "anyof.yaml"),
    ("recursive_self", FIXTURES / "edge" / "recursive_self.yaml"),
    ("recursive_mutual", FIXTURES / "edge" / "recursive_mutual.yaml"),
]


@pytest.mark.parametrize(("name", "spec_path"), GOLDEN_CASES)
def test_golden(name: str, spec_path: Path, tmp_path: Path):
    out = tmp_path / name
    generate_client(spec_path, out)
    golden = GOLDEN / name

    if os.environ.get("UPDATE_GOLDENS") == "1":
        if golden.exists():
            shutil.rmtree(golden)
        shutil.copytree(out, golden)

    if not golden.exists():
        pytest.fail(f"No golden for {name!r}. Run with UPDATE_GOLDENS=1 to create.")

    generated_files = {p.relative_to(out) for p in out.rglob("*.py")}
    golden_files = {p.relative_to(golden) for p in golden.rglob("*.py")}
    assert generated_files == golden_files, f"File set differs for {name}"

    for rel in sorted(generated_files):
        assert (out / rel).read_text() == (golden / rel).read_text(), (
            f"Diff in {name}/{rel}. Re-run with UPDATE_GOLDENS=1 if intentional."
        )
