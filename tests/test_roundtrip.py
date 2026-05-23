import importlib
import importlib.util
import json
import sys
from pathlib import Path

from pydantic import TypeAdapter

from openapi_pyx.generate import generate_client

FIXTURES = Path(__file__).parent / "fixtures"
EXPECTED_PETS_COUNT = 2


def _generate_and_load(tmp_path: Path):
    out = tmp_path / "petstore_client"
    generate_client(FIXTURES / "petstore.yaml", out)
    spec = importlib.util.spec_from_file_location(
        "petstore_client",
        out / "__init__.py",
        submodule_search_locations=[str(out)],
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["petstore_client"] = module
    spec.loader.exec_module(module)
    return importlib.import_module("petstore_client.models")


def _load_generated_models(tmp_path: Path, spec_path: Path, module_name: str):
    out = tmp_path / module_name
    generate_client(spec_path, out)
    spec = importlib.util.spec_from_file_location(
        module_name,
        out / "__init__.py",
        submodule_search_locations=[str(out)],
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return importlib.import_module(f"{module_name}.models")


def test_sanitized_field_model_round_trips_alias_and_python_name(tmp_path: Path):
    models = _load_generated_models(
        tmp_path,
        FIXTURES / "edge" / "sanitized_field.yaml",
        "sanitized_field_client",
    )
    # Accept the wire (original) name as input.
    item_via_alias = models.Item.model_validate({"class": "X", "for": 7})
    assert item_via_alias.class_ == "X"
    assert item_via_alias.for_ == 7
    # Accept the Python-safe name as input (populate_by_name).
    item_via_python = models.Item.model_validate({"class_": "Y"})
    assert item_via_python.class_ == "Y"
    # Output uses the wire name when by_alias=True.
    dumped = item_via_alias.model_dump_json(by_alias=True, exclude_none=True)
    assert '"class":"X"' in dumped
    assert '"for":7' in dumped


def test_schema_examples_render_into_field_examples(tmp_path: Path):
    models = _load_generated_models(
        tmp_path,
        FIXTURES / "edge" / "field_examples.yaml",
        "field_examples_client",
    )
    schema = models.Pet.model_json_schema()
    assert schema["properties"]["id"]["examples"] == [1, 42, 100]
    assert schema["properties"]["name"]["examples"] == ["Rex", "Whiskers"]
    # Deprecated singular `example` is normalized into the `examples` list.
    assert schema["properties"]["legacy"]["examples"] == ["legacy-value"]


def test_optional_union_with_null_member_accepts_string_and_null(tmp_path: Path):
    models = _load_generated_models(
        tmp_path,
        FIXTURES / "edge" / "optional_union_with_null.yaml",
        "optional_union_with_null_client",
    )
    assert models.Holder.model_validate({"any_of_with_null": "ok"}).any_of_with_null == "ok"
    assert models.Holder.model_validate({"any_of_with_null": None}).any_of_with_null is None
    assert models.Holder.model_validate({}).any_of_with_null is None


def test_pet_model_validates_real_payload(tmp_path: Path):
    models = _generate_and_load(tmp_path)
    payload = json.loads((FIXTURES / "payloads" / "petstore_pet.json").read_text())
    pet = models.Pet.model_validate(payload)
    assert pet.id == 1
    assert pet.name == "Rex"
    assert pet.tag == "good_boy"


def test_pets_alias_validates_real_payload(tmp_path: Path):
    models = _generate_and_load(tmp_path)
    payload = json.loads((FIXTURES / "payloads" / "petstore_pets.json").read_text())
    adapter = TypeAdapter(models.Pets)
    pets = adapter.validate_python(payload)
    assert len(pets) == EXPECTED_PETS_COUNT
    assert pets[1].name == "Whiskers"
