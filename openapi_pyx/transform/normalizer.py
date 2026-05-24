"""Pre-lowering normalization: collapse allOf into composed object schemas."""

from __future__ import annotations

from typing import TYPE_CHECKING

from openapi_pydantic.v3.v3_1 import DataType, Reference, Schema

from openapi_pyx.transform import COMPONENT_PREFIX

if TYPE_CHECKING:
    from openapi_pyx.transform.resolver import SchemaIndex


def compose_allof(schema: Schema, index: SchemaIndex) -> Schema:
    """Return a Schema with `allOf` merged into top-level properties/required.

    Refs inside `allOf` are followed and themselves composed. When every branch is
    object-shaped (or carries no type), branches are merged property-by-property and
    the result is typed as `object`. When at least one branch is primitive-shaped, the
    allOf is treated as a refinement of that primitive: the first non-object branch is
    returned and other branches' metadata is discarded. Real specs use the latter
    pattern to attach descriptions/constraints to a referenced primitive type.
    """
    if not schema.allOf:
        return schema

    composed_branches = [compose_allof(_follow(b, index), index) for b in schema.allOf]
    primitive_branch = next(
        (b for b in composed_branches if b.type not in (None, DataType.OBJECT) and not b.properties),
        None,
    )
    if primitive_branch is not None:
        # Primitive refinement; return the primitive branch and drop the rest.
        return primitive_branch.model_copy(update={"allOf": None})

    merged_props: dict[str, Schema | Reference] = {}
    merged_required: set[str] = set()
    for composed in composed_branches:
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
        if not node.ref.startswith(COMPONENT_PREFIX):
            raise ValueError(f"Unsupported $ref in allOf: {node.ref!r}")
        name = node.ref.removeprefix(COMPONENT_PREFIX)
        target = index.schemas.get(name)
        if target is None:
            raise ValueError(f"allOf references unknown schema: {name!r}")
        return target
    return node
