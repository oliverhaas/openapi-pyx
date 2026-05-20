import ast
import importlib.util
import sys
from pathlib import Path

from openapi_pyx.generate import generate_client

FIXTURES = Path(__file__).parent / "fixtures"


def test_petstore_generates_expected_layout(tmp_path: Path):
    out = tmp_path / "petstore_client"
    generate_client(FIXTURES / "petstore.yaml", out)

    assert (out / "__init__.py").exists()
    assert (out / "models.py").exists()
    assert (out / "client.py").exists()
    assert (out / "clients" / "__init__.py").exists()
    assert (out / "clients" / "pets.py").exists()


def test_generated_files_are_valid_python(tmp_path: Path):
    out = tmp_path / "petstore_client"
    generate_client(FIXTURES / "petstore.yaml", out)
    for f in out.rglob("*.py"):
        ast.parse(f.read_text())  # raises on syntax errors


def test_generated_client_imports_at_runtime(tmp_path: Path):
    out = tmp_path / "petstore_client"
    generate_client(FIXTURES / "petstore.yaml", out)
    spec = importlib.util.spec_from_file_location(
        "petstore_client",
        out / "__init__.py",
        submodule_search_locations=[str(out)],
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert hasattr(module, "Client")
