"""Normalized schema IR (post-lowering)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from collections.abc import Mapping

PrimitiveKind = Literal["string", "integer", "number", "boolean", "null"]


@dataclass(frozen=True, slots=True)
class PrimitiveSchema:
    kind: PrimitiveKind
    format: str | None = None
    nullable: bool = False
    enum_values: list[Any] = field(default_factory=list)
    # Pydantic Field kwargs keyed by their pydantic name (e.g. {"ge": 1, "le": 3, "max_length": 256}).
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ArraySchema:
    items: Schema
    nullable: bool = False


@dataclass(frozen=True, slots=True)
class SchemaField:
    name: str
    schema: Schema
    required: bool
    description: str | None = None
    examples: list[Any] = field(default_factory=list)
    serialization_alias: str | None = None  # set when name != original property name


@dataclass(frozen=True, slots=True)
class ObjectSchema:
    fields: list[SchemaField]
    additional_properties: Schema | None | Literal["any"] = None
    nullable: bool = False


@dataclass(frozen=True, slots=True)
class NamedSchemaRef:
    """Reference to a top-level named schema. `recursive` is set if part of a cycle."""

    name: str
    recursive: bool = False
    nullable: bool = False


@dataclass(frozen=True, slots=True)
class DiscriminatedUnion:
    """`oneOf` lowered with an explicit `discriminator.propertyName`."""

    property_name: str
    mapping: Mapping[str, NamedSchemaRef]
    nullable: bool = False


@dataclass(frozen=True, slots=True)
class TaggedUnion:
    """`oneOf`/`anyOf` lowered without a discriminator: tried in order via model_validator."""

    members: list[Schema]
    nullable: bool = False


@dataclass(frozen=True, slots=True)
class FreeFormSchema:
    """`additionalProperties: true` with no schema, or `{}` schema."""

    nullable: bool = False


Schema = (
    PrimitiveSchema | ArraySchema | ObjectSchema | NamedSchemaRef | DiscriminatedUnion | TaggedUnion | FreeFormSchema
)


@dataclass(frozen=True, slots=True)
class NamedSchema:
    """A top-level schema component, addressable by name."""

    name: str
    schema: Schema
    description: str | None = None
    examples: list[Any] = field(default_factory=list)
