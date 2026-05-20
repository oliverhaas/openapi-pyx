"""Top-level normalized document IR (schemas + tagged operations)."""

from __future__ import annotations

from dataclasses import dataclass

from openapi_pyx.ir.operation import Operation  # noqa: TC001
from openapi_pyx.ir.schema import NamedSchema  # noqa: TC001


@dataclass(frozen=True, slots=True)
class TagGroup:
    name: str  # OpenAPI tag (e.g. "pets")
    operations: list[Operation]


@dataclass(frozen=True, slots=True)
class Document:
    title: str
    schemas: list[NamedSchema]
    tags: list[TagGroup]
