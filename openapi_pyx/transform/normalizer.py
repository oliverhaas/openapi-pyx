"""Pre-lowering normalization: collapse allOf into composed object schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING

from openapi_pydantic.v3.v3_1 import DataType, Reference, Schema

if TYPE_CHECKING:
    from openapi_pyx.transform.resolver import SchemaIndex

_COMPONENT_PREFIX = "#/components/schemas/"


def compose_allof(schema: Schema, index: SchemaIndex) -> Schema:
    """Return a Schema with `allOf` merged into top-level properties/required.

    Refs inside `allOf` are followed and themselves composed. Non-object branches are
    a runtime error (we do not currently merge primitive constraints).
    """
    if not schema.allOf:
        return schema

    merged_props: dict[str, Schema | Reference] = {}
    merged_required: set[str] = set()
    for branch in schema.allOf:
        resolved = _follow(branch, index)
        composed = compose_allof(resolved, index)
        if composed.type not in (None, DataType.OBJECT) and composed.properties is None:
            raise ValueError("openapi-pyx v0.1 only supports object branches in allOf")
        merged_props.update(composed.properties or {})
        merged_required.update(composed.required or ())

    # Own top-level properties/required take precedence (override allOf branches).
    merged_props.update(schema.properties or {})
    merged_required.update(schema.required or ())

    return schema.model_copy(
        update={
            "allOf": None,
            "type": DataType.OBJECT,
            "properties": merged_props,
            "required": sorted(merged_required),
        },
    )


def _follow(node: Schema | Reference, index: SchemaIndex) -> Schema:
    if isinstance(node, Reference):
        if not node.ref.startswith(_COMPONENT_PREFIX):
            raise ValueError(f"Unsupported $ref in allOf: {node.ref!r}")
        return index.schemas[node.ref.removeprefix(_COMPONENT_PREFIX)]
    return node
