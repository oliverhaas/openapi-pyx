"""Lower spec-IR schemas into normalized IR."""

from __future__ import annotations

from openapi_pydantic.v3.v3_1 import DataType, Reference, Schema

from openapi_pyx.ir.schema import (
    ArraySchema,
    FreeFormSchema,
    NamedSchema,
    NamedSchemaRef,
    ObjectSchema,
    PrimitiveSchema,
    SchemaField,
)
from openapi_pyx.ir.schema import Schema as IRSchema
from openapi_pyx.transform.resolver import SchemaIndex  # noqa: TC001

_PRIMITIVE_KINDS = {DataType.STRING, DataType.INTEGER, DataType.NUMBER, DataType.BOOLEAN, DataType.NULL}
_COMPONENT_PREFIX = "#/components/schemas/"


def lower_components(index: SchemaIndex) -> list[NamedSchema]:
    """Lower every top-level component schema."""
    return [
        NamedSchema(name=name, schema=_lower(schema, index), description=schema.description)
        for name, schema in index.schemas.items()
    ]


def _lower(schema: Schema | Reference, index: SchemaIndex) -> IRSchema:
    if isinstance(schema, Reference):
        return _ref_to_named(schema.ref, index)

    nullable, types = _split_nullable(schema.type)

    if DataType.ARRAY in types or schema.items is not None:
        items = _lower(schema.items, index) if schema.items is not None else FreeFormSchema()
        return ArraySchema(items=items, nullable=nullable)

    if DataType.OBJECT in types or schema.properties is not None or schema.additionalProperties is not None:
        return _lower_object(schema, index, nullable=nullable)

    if types and all(t in _PRIMITIVE_KINDS for t in types):
        # take the first non-null primitive
        kind = next(t for t in types if t != DataType.NULL)
        return PrimitiveSchema(kind=kind.value, format=schema.schema_format, nullable=nullable)

    return FreeFormSchema(nullable=nullable)


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
    if not ref.startswith(_COMPONENT_PREFIX):
        raise ValueError(f"Unsupported $ref: {ref!r}")
    name = ref.removeprefix(_COMPONENT_PREFIX)
    return NamedSchemaRef(name=name, recursive=name in index.recursive_names)
