from pathlib import Path

from openapi_pyx.ingest.loader import load_spec
from openapi_pyx.transform.resolver import build_schema_index

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


def test_inlines_top_level_ref_alias_in_components(tmp_path):
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
    index = build_schema_index(spec)
    # The loader inlines `Alias: {$ref: Real}` into Real's content, so Alias
    # is a real schema with the same properties.
    assert "Real" in index.schemas
    assert "Alias" in index.schemas
    assert index.schemas["Alias"].properties == index.schemas["Real"].properties


def test_inlines_cross_path_ref(tmp_path):
    """Cross-path `$ref`s (e.g. Scayle's response dedup) are inlined at load time."""
    p = tmp_path / "cross-path.yaml"
    p.write_text(
        "openapi: 3.1.0\n"
        "info: { title: x, version: '1' }\n"
        "paths:\n"
        "  /a:\n"
        "    get:\n"
        "      responses:\n"
        '        "200":\n'
        "          description: ok\n"
        "          content:\n"
        "            application/json:\n"
        "              schema: { type: object, properties: { id: { type: integer } } }\n"
        "  /b:\n"
        "    get:\n"
        "      responses:\n"
        '        "200":\n'
        "          description: ok\n"
        "          content:\n"
        "            application/json:\n"
        '              schema: { $ref: "#/paths/~1a/get/responses/200/content/application~1json/schema" }\n',
    )
    spec = load_spec(p)
    b_schema = spec.paths["/b"].get.responses["200"].content["application/json"].media_type_schema
    assert b_schema.type == "object"
    assert "id" in (b_schema.properties or {})
