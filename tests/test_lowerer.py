from pathlib import Path

from openapi_pyx.ingest.loader import load_spec
from openapi_pyx.ir.schema import (
    ArraySchema,
    DiscriminatedUnion,
    NamedSchemaRef,
    ObjectSchema,
    PrimitiveSchema,
    TaggedUnion,
)
from openapi_pyx.transform.lowerer import lower_components
from openapi_pyx.transform.resolver import build_schema_index

FIXTURES = Path(__file__).parent / "fixtures"


def _lower(name: str):
    spec = load_spec(FIXTURES / "edge" / f"{name}.yaml")
    index = build_schema_index(spec)
    return lower_components(index)


def test_primitives_lowered():
    schemas = _lower("primitives")
    atoms = next(ns for ns in schemas if ns.name == "Atoms")
    assert isinstance(atoms.schema, ObjectSchema)
    fields = {f.name: f for f in atoms.schema.fields}
    assert fields["s"].required and isinstance(fields["s"].schema, PrimitiveSchema)
    assert fields["s"].schema.kind == "string"
    assert fields["i"].schema.kind == "integer"
    assert fields["n"].schema.kind == "number" and fields["n"].schema.format == "float"
    assert fields["b"].schema.kind == "boolean"
    assert fields["opt_s"].schema.nullable is True
    assert fields["opt_s"].required is False


def test_nullable_array_lowered():
    schemas = _lower("nullable_array")
    bag = next(ns for ns in schemas if ns.name == "Bag").schema
    assert isinstance(bag, ObjectSchema)
    items = next(f for f in bag.fields if f.name == "items").schema
    assert isinstance(items, ArraySchema)
    assert items.nullable is True
    assert isinstance(items.items, PrimitiveSchema)
    assert items.items.kind == "string"


def test_allof_composes_required_and_properties():
    schemas = _lower("allof_compose")
    named = next(ns for ns in schemas if ns.name == "Named").schema
    assert isinstance(named, ObjectSchema)
    fields = {f.name: f for f in named.fields}
    assert fields["id"].required is True
    assert fields["name"].required is True


def test_oneof_with_discriminator_lowered():
    schemas = _lower("oneof_discriminator")
    animal = next(ns for ns in schemas if ns.name == "Animal").schema
    assert isinstance(animal, DiscriminatedUnion)
    assert animal.property_name == "kind"
    assert set(animal.mapping) == {"dog", "cat"}
    assert all(isinstance(v, NamedSchemaRef) for v in animal.mapping.values())


def test_oneof_without_discriminator_is_tagged_union():
    schemas = _lower("oneof_no_discriminator")
    either = next(ns for ns in schemas if ns.name == "Either").schema
    assert isinstance(either, TaggedUnion)
    expected_members = 2
    assert len(either.members) == expected_members


def test_anyof_is_tagged_union():
    schemas = _lower("anyof")
    soi = next(ns for ns in schemas if ns.name == "StringOrInt").schema
    assert isinstance(soi, TaggedUnion)
    expected_members = 2
    assert len(soi.members) == expected_members
