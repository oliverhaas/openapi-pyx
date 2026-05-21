"""$ref resolution + recursion detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from openapi_pydantic.v3.v3_1 import OpenAPI, Schema

from openapi_pyx.transform import COMPONENT_PREFIX

if TYPE_CHECKING:
    from collections.abc import Iterator


class ResolveError(ValueError):
    """Raised when a $ref cannot be resolved or has an unsupported shape."""


@dataclass(slots=True)
class SchemaIndex:
    """Indexed view of `components.schemas` with recursion classification."""

    schemas: dict[str, Schema]
    recursive_names: set[str] = field(default_factory=set)


def build_schema_index(spec: OpenAPI) -> SchemaIndex:
    """Build an index of schemas and identify recursive definitions."""
    _validate_refs_targets(spec)

    components = spec.components
    if components is None or not components.schemas:
        return SchemaIndex(schemas={})

    schemas: dict[str, Schema] = {}
    for name, schema in components.schemas.items():
        if not isinstance(schema, Schema) or (schema.model_extra or {}).get("$ref"):
            raise ResolveError(
                f"components.schemas.{name} is a top-level $ref alias. "
                "These aren't supported in v0.1; inline the target schema instead.",
            )
        schemas[name] = schema

    recursive = _find_recursive(schemas)
    return SchemaIndex(schemas=schemas, recursive_names=recursive)


def _validate_refs_targets(spec: OpenAPI) -> None:
    """Walk the entire spec; every $ref must point at `#/components/schemas/…`."""
    for ref in _iter_refs(spec.model_dump(by_alias=True, exclude_none=True)):
        if not ref.startswith(COMPONENT_PREFIX):
            raise ResolveError(f"Only $refs to components/schemas are supported in v0.1; got {ref!r}")


def _iter_refs(node: Any) -> Iterator[str]:  # noqa: ANN401
    """Recursively find all $ref values in a nested structure."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref" and isinstance(v, str):
                yield v
            else:
                yield from _iter_refs(v)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_refs(item)


def _find_recursive(schemas: dict[str, Schema]) -> set[str]:
    """Tarjan-style SCC detection over the ref graph; nodes in any non-trivial SCC are recursive."""
    graph = {name: _refs_in(schema) & schemas.keys() for name, schema in schemas.items()}
    return _strongly_connected_recursives(graph)


def _refs_in(schema: Schema) -> set[str]:
    """Extract schema names from $refs in a schema."""
    dumped = schema.model_dump(by_alias=True, exclude_none=True)
    return {ref.removeprefix(COMPONENT_PREFIX) for ref in _iter_refs(dumped) if ref.startswith(COMPONENT_PREFIX)}


def _strongly_connected_recursives(graph: dict[str, set[str]]) -> set[str]:  # noqa: C901
    """Find all nodes that are part of a non-trivial SCC using Tarjan's algorithm."""
    index_of: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: set[str] = set()
    stack: list[str] = []
    result: set[str] = set()
    counter = 0

    def visit(v: str) -> None:
        nonlocal counter
        index_of[v] = lowlink[v] = counter
        counter += 1
        stack.append(v)
        on_stack.add(v)
        for w in graph.get(v, ()):
            if w not in index_of:
                visit(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif w in on_stack:
                lowlink[v] = min(lowlink[v], index_of[w])
        if lowlink[v] == index_of[v]:
            scc: list[str] = []
            while True:
                w = stack.pop()
                on_stack.discard(w)
                scc.append(w)
                if w == v:
                    break
            if len(scc) > 1 or v in graph.get(v, ()):
                result.update(scc)

    for node in graph:
        if node not in index_of:
            visit(node)
    return result
