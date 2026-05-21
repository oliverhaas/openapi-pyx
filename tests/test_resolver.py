from pathlib import Path

import pytest

from openapi_pyx.ingest.loader import load_spec
from openapi_pyx.transform.resolver import ResolveError, build_schema_index

FIXTURES = Path(__file__).parent / "fixtures"


def test_petstore_no_recursion():
    spec = load_spec(FIXTURES / "petstore.yaml")
    index = build_schema_index(spec)
    assert "Pet" in index.schemas
    assert "Pets" in index.schemas
    assert index.recursive_names == set()


def test_self_recursive_marked():
    spec = load_spec(FIXTURES / "edge" / "recursive_self.yaml")
    index = build_schema_index(spec)
    assert "Node" in index.recursive_names


def test_mutually_recursive_both_marked():
    spec = load_spec(FIXTURES / "edge" / "recursive_mutual.yaml")
    index = build_schema_index(spec)
    assert {"A", "B"} <= index.recursive_names


def test_rejects_top_level_ref_alias_in_components(tmp_path):
    p = tmp_path / "alias.yaml"
    p.write_text(
        "openapi: 3.1.0\n"
        "info: { title: x, version: '1' }\n"
        "paths: {}\n"
        "components:\n"
        "  schemas:\n"
        "    Real:\n"
        "      type: object\n"
        "      properties: { id: { type: integer } }\n"
        '    Alias: { $ref: "#/components/schemas/Real" }\n',
    )
    spec = load_spec(p)
    with pytest.raises(ResolveError, match="top-level"):
        build_schema_index(spec)


def test_rejects_non_components_ref(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text(
        "openapi: 3.1.0\n"
        "info: { title: x, version: '1' }\n"
        "paths:\n"
        "  /x:\n"
        "    get:\n"
        "      responses:\n"
        '        "200":\n'
        "          description: y\n"
        "          content:\n"
        "            application/json:\n"
        '              schema: { $ref: "#/paths/~1x/get" }\n',
    )
    spec = load_spec(p)
    with pytest.raises(ResolveError, match="components/schemas"):
        build_schema_index(spec)
