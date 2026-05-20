from pathlib import Path

from openapi_pyx.codegen.emit_models import emit_models_module
from openapi_pyx.codegen.render import render_module
from openapi_pyx.ingest.loader import load_spec
from openapi_pyx.transform.lowerer import lower_components
from openapi_pyx.transform.resolver import build_schema_index

FIXTURES = Path(__file__).parent / "fixtures"


def _emit(name: str) -> str:
    spec = (
        load_spec(FIXTURES / "edge" / f"{name}.yaml") if name != "petstore" else load_spec(FIXTURES / "petstore.yaml")
    )
    index = build_schema_index(spec)
    schemas = lower_components(index)
    return render_module(emit_models_module(schemas))


def test_petstore_models_emit_classes_for_pet_and_pets():
    src = _emit("petstore")
    assert "from pydantic import BaseModel" in src
    assert "class Pet(BaseModel):" in src
    assert "    id: int" in src
    assert "    name: str" in src
    assert "    tag: str | None = None" in src
    # `Pets` is an array → emitted as a TypeAlias, not a class
    assert "Pets = list[Pet]" in src or "Pets: TypeAlias = list[Pet]" in src


def test_nullable_array_emits_list_or_none():
    src = _emit("nullable_array")
    assert "class Bag(BaseModel):" in src
    assert "    items: list[str] | None = None" in src


def test_recursive_self_uses_forward_ref_string():
    src = _emit("recursive_self")
    assert "class Node(BaseModel):" in src
    # forward ref expressed as a string (no `from __future__ import annotations`)
    assert '"Node"' in src or "Node | None" in src
    assert "__future__" not in src


def test_oneof_discriminator_emits_annotated_union():
    src = _emit("oneof_discriminator")
    assert "Discriminator" in src
    assert "Annotated[" in src
    assert "Dog" in src and "Cat" in src
