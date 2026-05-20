from pathlib import Path

import pytest

from openapi_pyx.ingest.loader import LoadError, load_spec

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_petstore_yaml():
    spec = load_spec(FIXTURES / "petstore.yaml")
    assert spec.openapi.startswith("3.1")
    assert spec.info.title == "Petstore"
    assert "/pets" in spec.paths


def test_rejects_openapi_3_0(tmp_path):
    p = tmp_path / "v3.yaml"
    p.write_text("openapi: 3.0.3\ninfo:\n  title: x\n  version: 1\npaths: {}\n")
    with pytest.raises(LoadError, match=r"3\.1"):
        load_spec(p)


def test_rejects_missing_paths(tmp_path):
    p = tmp_path / "no-paths.yaml"
    p.write_text("openapi: 3.1.0\ninfo:\n  title: x\n  version: 1\n")
    with pytest.raises(LoadError):
        load_spec(p)
