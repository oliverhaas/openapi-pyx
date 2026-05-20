from pathlib import Path

from openapi_pyx.codegen.emit_clients import emit_client_module
from openapi_pyx.codegen.render import render_module
from openapi_pyx.ingest.loader import load_spec
from openapi_pyx.transform.lowerer import lower_components
from openapi_pyx.transform.operations import build_document
from openapi_pyx.transform.resolver import build_schema_index

FIXTURES = Path(__file__).parent / "fixtures"


def _emit_pets_client() -> str:
    spec = load_spec(FIXTURES / "petstore.yaml")
    index = build_schema_index(spec)
    schemas = lower_components(index)
    doc = build_document(spec, index, schemas)
    pets_group = next(t for t in doc.tags if t.name == "pets")
    return render_module(emit_client_module(pets_group))


def test_pets_client_imports_httpx_and_models():
    src = _emit_pets_client()
    assert "import httpx" in src
    assert "from ..models import" in src
    assert "Pet" in src
    assert "Pets" in src


def test_pets_client_class_has_methods():
    src = _emit_pets_client()
    assert "class PetsClient:" in src
    assert "async def list_pets(" in src
    assert "async def create_pet(" in src
    assert "async def show_pet_by_id(" in src


def test_list_pets_has_keyword_only_limit_with_default_none():
    src = _emit_pets_client()
    assert "*, limit: int | None = None" in src


def test_show_pet_by_id_uses_fstring_path():
    src = _emit_pets_client()
    assert 'await self._http.get(f"/pets/{pet_id}"' in src


def test_create_pet_posts_body_json():
    src = _emit_pets_client()
    assert "body.model_dump_json" in src


def test_emits_typeadapter_for_response_models():
    src = _emit_pets_client()
    assert "TypeAdapter" in src
    assert ".validate_json(resp.content)" in src


def test_optional_body_emits_runtime_conditional():
    spec = load_spec(FIXTURES / "edge" / "optional_body.yaml")
    index = build_schema_index(spec)
    schemas = lower_components(index)
    doc = build_document(spec, index, schemas)
    group = next(t for t in doc.tags if t.name == "pets")
    src = render_module(emit_client_module(group))
    # The body parameter is Optional (defaults to None)
    assert "body: Pet | None = None" in src
    # The renderer must guard the content= arg behind an `if body is not None:` check
    assert "if body is not None:" in src
    # And there must be a fallback call without the content= arg
    assert src.count('await self._http.put("/pets"') == 2
