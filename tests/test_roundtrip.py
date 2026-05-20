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
