from openapi_pyx.ir.schema import (
    DiscriminatedUnion,
    EnumSchema,
    LiteralSchema,
    NamedSchemaRef,
    ObjectSchema,
    PrimitiveSchema,
    SchemaField,
    TaggedUnion,
)


def test_primitive_schema_carries_format_and_nullable():
    s = PrimitiveSchema(kind="string", format=None, nullable=True)
    assert s.kind == "string"
    assert s.nullable is True


def test_object_schema_lists_required_fields():
    schema = ObjectSchema(
        fields=[
            SchemaField(name="id", schema=PrimitiveSchema(kind="integer"), required=True),
            SchemaField(name="name", schema=PrimitiveSchema(kind="string"), required=False),
        ],
        additional_properties=None,
    )
    assert [f.name for f in schema.fields if f.required] == ["id"]


def test_named_ref_is_recursive_aware():
    ref = NamedSchemaRef(name="Node", recursive=True)
    assert ref.recursive is True


def test_discriminated_union_has_propertyname_and_mapping():
    u = DiscriminatedUnion(
        property_name="kind",
        mapping={"dog": NamedSchemaRef(name="Dog"), "cat": NamedSchemaRef(name="Cat")},
    )
    assert u.property_name == "kind"


def test_tagged_union_carries_member_schemas():
    members_count = 2
    u = TaggedUnion(members=[NamedSchemaRef("Foo"), NamedSchemaRef("Bar")])
    assert len(u.members) == members_count


def test_literal_schema_holds_values():
    s = LiteralSchema(values=["a", "b"])
    assert s.values == ["a", "b"]


def test_enum_schema_is_named():
    s = EnumSchema(name="Color", values=["red", "green"])
    assert s.name == "Color"
