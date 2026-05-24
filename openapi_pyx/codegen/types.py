"""Render normalized IR schemas as Python type expressions.

Used by the client codegen for parameter/return type annotations.
Models themselves are emitted by `datamodel-code-generator`, which we
don't drive through this renderer.
"""

from openapi_pyx.ir.schema import (
    ArraySchema,
    DiscriminatedUnion,
    FreeFormSchema,
    NamedSchemaRef,
    ObjectSchema,
    PrimitiveSchema,
    Schema,
    TaggedUnion,
)
from openapi_pyx.naming import model_name

_PRIMITIVE_PY = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "null": "None",
}


def render_type(schema: Schema) -> str:  # noqa: PLR0911
    if isinstance(schema, PrimitiveSchema):
        if schema.enum_values:
            base = f"Literal[{', '.join(repr(v) for v in schema.enum_values)}]"
        else:
            base = _PRIMITIVE_PY[schema.kind]
        return f"{base} | None" if schema.nullable else base
    if isinstance(schema, ArraySchema):
        inner = render_type(schema.items)
        out = f"list[{inner}]"
        return f"{out} | None" if schema.nullable else out
    if isinstance(schema, NamedSchemaRef):
        ref = f'"{model_name(schema.name)}"' if schema.recursive else model_name(schema.name)
        return f"{ref} | None" if schema.nullable else ref
    if isinstance(schema, FreeFormSchema):
        return "Any | None" if schema.nullable else "Any"
    if isinstance(schema, ObjectSchema):
        return "dict[str, Any]"
    if isinstance(schema, TaggedUnion):
        return render_tagged_union(schema)
    if isinstance(schema, DiscriminatedUnion):
        return " | ".join(model_name(ref.name) for ref in schema.mapping.values())
    raise TypeError(f"Unsupported schema for rendering: {schema!r}")


def render_tagged_union(u: TaggedUnion) -> str:
    members = " | ".join(render_type(m) for m in u.members)
    return f"{members} | None" if u.nullable else members


def renders_with_none(schema: Schema) -> bool:
    """Whether `render_type(schema)` already produces a type that admits None."""
    if isinstance(schema, PrimitiveSchema):
        return schema.nullable or schema.kind == "null"
    if isinstance(schema, TaggedUnion):
        return schema.nullable or any(renders_with_none(m) for m in schema.members)
    return getattr(schema, "nullable", False)
