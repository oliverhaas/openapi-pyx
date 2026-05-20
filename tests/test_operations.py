from pathlib import Path

from openapi_pyx.ingest.loader import load_spec
from openapi_pyx.ir.operation import ParamLocation
from openapi_pyx.ir.schema import NamedSchemaRef
from openapi_pyx.transform.lowerer import lower_components
from openapi_pyx.transform.operations import build_document
from openapi_pyx.transform.resolver import build_schema_index

FIXTURES = Path(__file__).parent / "fixtures"


def test_petstore_document_groups_by_tag():
    spec = load_spec(FIXTURES / "petstore.yaml")
    index = build_schema_index(spec)
    schemas = lower_components(index)
    doc = build_document(spec, index, schemas)

    assert {tag.name for tag in doc.tags} == {"pets"}
    pets = next(t for t in doc.tags if t.name == "pets")
    assert {op.operation_id for op in pets.operations} == {
        "listPets",
        "createPet",
        "showPetById",
    }


def test_list_pets_has_query_param_and_response_type():
    spec = load_spec(FIXTURES / "petstore.yaml")
    index = build_schema_index(spec)
    schemas = lower_components(index)
    doc = build_document(spec, index, schemas)

    list_pets = next(op for tag in doc.tags for op in tag.operations if op.operation_id == "listPets")
    assert list_pets.http_method == "get"
    assert list_pets.path == "/pets"
    assert len(list_pets.parameters) == 1
    p = list_pets.parameters[0]
    assert p.name == "limit"
    assert p.location is ParamLocation.QUERY
    assert p.required is False
    assert list_pets.response is not None
    assert isinstance(list_pets.response.schema, NamedSchemaRef)
    assert list_pets.response.schema.name == "Pets"


def test_show_pet_by_id_has_path_param():
    spec = load_spec(FIXTURES / "petstore.yaml")
    index = build_schema_index(spec)
    schemas = lower_components(index)
    doc = build_document(spec, index, schemas)

    op = next(o for tag in doc.tags for o in tag.operations if o.operation_id == "showPetById")
    p = op.parameters[0]
    assert p.name == "petId"
    assert p.location is ParamLocation.PATH
    assert p.required is True


def test_create_pet_has_body_and_no_response():
    spec = load_spec(FIXTURES / "petstore.yaml")
    index = build_schema_index(spec)
    schemas = lower_components(index)
    doc = build_document(spec, index, schemas)

    op = next(o for tag in doc.tags for o in tag.operations if o.operation_id == "createPet")
    assert op.request_body is not None
    assert isinstance(op.request_body.schema, NamedSchemaRef)
    assert op.request_body.schema.name == "Pet"
    assert op.response is None
