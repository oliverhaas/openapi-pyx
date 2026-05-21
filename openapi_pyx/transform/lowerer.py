"""Lower spec-IR schemas into normalized IR."""

from __future__ import annotations

from openapi_pydantic.v3.v3_1 import DataType, Reference, Schema

from openapi_pyx.ir.schema import (
    ArraySchema,
    DiscriminatedUnion,
    FreeFormSchema,
    NamedSchema,
    NamedSchemaRef,
    ObjectSchema,
    PrimitiveKind,
    PrimitiveSchema,
    SchemaField,
    TaggedUnion,
)
from openapi_pyx.ir.schema import Schema as IRSchema
from openapi_pyx.transform import COMPONENT_PREFIX
from openapi_pyx.transform.normalizer import compose_allof
from openapi_pyx.transform.resolver import SchemaIndex  # noqa: TC001

_DATATYPE_TO_KIND: dict[DataType, PrimitiveKind] = {
    DataType.STRING: "string",
    DataType.INTEGER: "integer",
    DataType.NUMBER: "number",
    DataType.BOOLEAN: "boolean",
    DataType.NULL: "null",
}


def lower_components(index: SchemaIndex) -> list[NamedSchema]:
    """Lower every top-level component schema."""
    return [
        NamedSchema(name=name, schema=_lower(schema, index), description=schema.description)
        for name, schema in index.schemas.items()
    ]


def _lower(schema: Schema | Reference, index: SchemaIndex) -> IRSchema:  # noqa: PLR0911
    if isinstance(schema, Reference):
        return _ref_to_named(schema.ref, index)

    # Collapse allOf so downstream code never sees it.
    if schema.allOf:
        schema = compose_allof(schema, index)

    if schema.discriminator and schema.oneOf:
        return _lower_discriminated_oneof(schema, index)

    if schema.oneOf or schema.anyOf:
        members = [_lower(m, index) for m in (schema.oneOf or schema.anyOf or ())]
        nullable, _ = _split_nullable(schema.type)
        return TaggedUnion(members=members, nullable=nullable)

    nullable, types = _split_nullable(schema.type)

    if DataType.ARRAY in types or schema.items is not None:
        items = _lower(schema.items, index) if schema.items is not None else FreeFormSchema()
        return ArraySchema(items=items, nullable=nullable)

    if DataType.OBJECT in types or schema.properties is not None or schema.additionalProperties is not None:
        return _lower_object(schema, index, nullable=nullable)

    if types and all(t in _DATATYPE_TO_KIND for t in types):
        # Take the first non-null primitive, falling back to "null" itself
        # when that's the only declared type.
        kind = next((t for t in types if t != DataType.NULL), DataType.NULL)
        return PrimitiveSchema(kind=_DATATYPE_TO_KIND[kind], format=schema.schema_format, nullable=nullable)

    return FreeFormSchema(nullable=nullable)


def _lower_discriminated_oneof(schema: Schema, index: SchemaIndex) -> DiscriminatedUnion:
    disc = schema.discriminator
    if disc is None or not disc.propertyName:
        raise ValueError("Discriminated oneOf must have propertyName")

    mapping: dict[str, NamedSchemaRef] = {}
    if disc.mapping:
        for tag, ref in disc.mapping.items():
            if not isinstance(ref, str) or not ref.startswith(COMPONENT_PREFIX):
                raise ValueError(f"Discriminator mapping must reference components/schemas: {ref!r}")
            name = ref.removeprefix(COMPONENT_PREFIX)
            mapping[tag] = NamedSchemaRef(name=name, recursive=name in index.recursive_names)
    else:
        for branch in schema.oneOf or ():
            if not isinstance(branch, Reference):
                raise TypeError("Discriminated oneOf branches must be $refs")
            name = branch.ref.removeprefix(COMPONENT_PREFIX)
            mapping[name] = NamedSchemaRef(name=name, recursive=name in index.recursive_names)

    return DiscriminatedUnion(property_name=disc.propertyName, mapping=mapping)


def _lower_object(schema: Schema, index: SchemaIndex, *, nullable: bool) -> ObjectSchema:
    required = set(schema.required or ())
    fields: list[SchemaField] = []
    for prop_name, prop_schema in (schema.properties or {}).items():
        fields.append(
            SchemaField(
                name=prop_name,
                schema=_lower(prop_schema, index),
                required=prop_name in required,
                description=getattr(prop_schema, "description", None),
            ),
        )

    additional: IRSchema | None | str
    ap = schema.additionalProperties
    if ap is None or ap is True:
        additional = "any" if ap is True else None
    elif ap is False:
        additional = None
    else:
        additional = _lower(ap, index)

    return ObjectSchema(fields=fields, additional_properties=additional, nullable=nullable)


def _split_nullable(type_field: object) -> tuple[bool, tuple[DataType, ...]]:
    if type_field is None:
        return False, ()
    if isinstance(type_field, DataType):
        return False, (type_field,)
    if isinstance(type_field, list):
        types = tuple(t for t in type_field if isinstance(t, DataType))
        return (DataType.NULL in types), tuple(t for t in types if t != DataType.NULL)
    return False, ()


def _ref_to_named(ref: str, index: SchemaIndex) -> NamedSchemaRef:
    if not ref.startswith(COMPONENT_PREFIX):
        raise ValueError(f"Unsupported $ref: {ref!r}")
    name = ref.removeprefix(COMPONENT_PREFIX)
    return NamedSchemaRef(name=name, recursive=name in index.recursive_names)
