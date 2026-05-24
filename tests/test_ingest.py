from pathlib import Path

import pytest

from openapi_pyx.ingest.loader import LoadError, load_spec

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_petstore_yaml():
    spec = load_spec(FIXTURES / "petstore.yaml")
    assert spec.openapi.startswith("3.1")
    assert spec.info.title == "Petstore"
    assert "/pets" in spec.paths


def test_accepts_openapi_3_0_and_normalizes_to_3_1(tmp_path):
    p = tmp_path / "v3.yaml"
    p.write_text(
        "openapi: 3.0.3\n"
        "info: { title: x, version: '1' }\n"
        "paths: {}\n"
        "components:\n"
        "  schemas:\n"
        "    Maybe:\n"
        "      type: string\n"
        "      nullable: true\n",
    )
    spec = load_spec(p)
    # 3.0 specs are bumped to 3.1.0 after normalization.
    assert spec.openapi.startswith("3.1")
    # `nullable: true` is rewritten into `type: [string, "null"]`.
    schema = spec.components.schemas["Maybe"]
    assert "null" in (schema.type if isinstance(schema.type, list) else [schema.type])


def test_rejects_unsupported_version(tmp_path):
    p = tmp_path / "v2.yaml"
    p.write_text("openapi: '2.0'\ninfo: { title: x, version: '1' }\npaths: {}\n")
    with pytest.raises(LoadError, match=r"3\.0 and 3\.1"):
        load_spec(p)


def test_rejects_missing_paths(tmp_path):
    p = tmp_path / "no-paths.yaml"
    p.write_text("openapi: 3.1.0\ninfo:\n  title: x\n  version: 1\n")
    with pytest.raises(LoadError):
        load_spec(p)
