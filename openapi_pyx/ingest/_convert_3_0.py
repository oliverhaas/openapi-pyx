"""Convert an OpenAPI 3.0 spec dict into 3.1 form.

We validate the input against `openapi_pydantic.v3.v3_0.OpenAPI` to catch malformed
3.0 specs early, then walk the raw dict at the exact positions where Schemas live
(per the 3.0 model structure) and rewrite each Schema's 3.0-only constructs to their
3.1 equivalents. Validation gives us safety; raw-dict mutation avoids a Pydantic V2
serializer bug we hit when mutating typed Schema fields inside nested Operation/
PathItem instances.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from openapi_pydantic.v3 import v3_0

SchemaFn = Callable[[dict[str, Any]], None]


def convert_3_0_to_3_1(raw: dict[str, Any]) -> dict[str, Any]:
    """Parse `raw` as v3.0, walk its Schema positions, return a v3.1-shaped dict.

    The walk is in-place on `raw`. Raises `pydantic.ValidationError` if the spec
    declares `openapi=3.0.x` but doesn't parse against the 3.0 model.
    """
    v3_0.OpenAPI.model_validate(raw)
    _visit_all_schemas(raw, _convert_schema_dict)
    raw["openapi"] = "3.1.0"
    return raw


def _convert_schema_dict(s: dict[str, Any]) -> None:
    """In-place 3.0 → 3.1 conversion for a single Schema dict.

    - `nullable: true` + `type: X` → drop `nullable`, set `type: [X, "null"]`.
    - `nullable: true|false` without `type` → drop `nullable` (3.0 says it's a no-op
      unless `type` is set, so we don't attempt to widen via anyOf).
    - `exclusiveMinimum: true` + `minimum: N` → numeric `exclusiveMinimum: N`.
    - `exclusiveMinimum: false` (a no-op flag in 3.0) → drop.
    - Same for `exclusiveMaximum`.
    """
    if s.pop("nullable", None) is True:
        existing = s.get("type")
        if isinstance(existing, str):
            s["type"] = [existing, "null"]

    _convert_exclusive_bound(s, bool_key="exclusiveMinimum", value_key="minimum")
    _convert_exclusive_bound(s, bool_key="exclusiveMaximum", value_key="maximum")


def _convert_exclusive_bound(s: dict[str, Any], *, bool_key: str, value_key: str) -> None:
    flag = s.get(bool_key)
    if not isinstance(flag, bool):
        return  # absent or already numeric (3.1 form)
    bound = s.get(value_key)
    if flag and isinstance(bound, int | float):
        s[bool_key] = bound
        s.pop(value_key, None)
    else:
        s.pop(bool_key, None)


# Walkers that follow the OpenAPI 3.0 dict structure. Each helper visits exactly the
# positions where its node-type can hold a Schema (directly or via nested objects).


def _visit_all_schemas(raw: dict[str, Any], fn: SchemaFn) -> None:
    components = raw.get("components")
    if isinstance(components, dict):
        for schema in (components.get("schemas") or {}).values():
            _visit_schema_or_ref(schema, fn)
        for param in (components.get("parameters") or {}).values():
            _visit_parameter(param, fn)
        for response in (components.get("responses") or {}).values():
            _visit_response(response, fn)
        for body in (components.get("requestBodies") or {}).values():
            _visit_request_body(body, fn)
        for header in (components.get("headers") or {}).values():
            _visit_header(header, fn)
    paths = raw.get("paths")
    if isinstance(paths, dict):
        for path_item in paths.values():
            _visit_path_item(path_item, fn)


def _visit_schema_or_ref(node: Any, fn: SchemaFn) -> None:  # noqa: ANN401
    if not isinstance(node, dict) or "$ref" in node:
        return
    fn(node)
    properties = node.get("properties")
    if isinstance(properties, dict):
        for value in properties.values():
            _visit_schema_or_ref(value, fn)
    for key in ("items", "not", "additionalProperties"):
        value = node.get(key)
        if isinstance(value, dict):
            _visit_schema_or_ref(value, fn)
    for key in ("allOf", "anyOf", "oneOf"):
        branches = node.get(key)
        if isinstance(branches, list):
            for branch in branches:
                _visit_schema_or_ref(branch, fn)


def _visit_media_type_map(content: Any, fn: SchemaFn) -> None:  # noqa: ANN401
    if not isinstance(content, dict):
        return
    for media in content.values():
        if isinstance(media, dict):
            _visit_schema_or_ref(media.get("schema"), fn)


def _visit_parameter(p: Any, fn: SchemaFn) -> None:  # noqa: ANN401
    if not isinstance(p, dict) or "$ref" in p:
        return
    _visit_schema_or_ref(p.get("schema"), fn)
    _visit_media_type_map(p.get("content"), fn)


def _visit_request_body(rb: Any, fn: SchemaFn) -> None:  # noqa: ANN401
    if not isinstance(rb, dict) or "$ref" in rb:
        return
    _visit_media_type_map(rb.get("content"), fn)


def _visit_response(r: Any, fn: SchemaFn) -> None:  # noqa: ANN401
    if not isinstance(r, dict) or "$ref" in r:
        return
    _visit_media_type_map(r.get("content"), fn)
    for header in (r.get("headers") or {}).values():
        _visit_header(header, fn)


def _visit_header(h: Any, fn: SchemaFn) -> None:  # noqa: ANN401
    if not isinstance(h, dict) or "$ref" in h:
        return
    _visit_schema_or_ref(h.get("schema"), fn)
    _visit_media_type_map(h.get("content"), fn)


_METHODS = ("get", "put", "post", "delete", "options", "head", "patch", "trace")


def _visit_path_item(pi: Any, fn: SchemaFn) -> None:  # noqa: ANN401
    if not isinstance(pi, dict) or "$ref" in pi:
        return
    for param in pi.get("parameters") or []:
        _visit_parameter(param, fn)
    for method in _METHODS:
        op = pi.get(method)
        if isinstance(op, dict):
            _visit_operation(op, fn)


def _visit_operation(op: dict[str, Any], fn: SchemaFn) -> None:
    for param in op.get("parameters") or []:
        _visit_parameter(param, fn)
    _visit_request_body(op.get("requestBody"), fn)
    for response in (op.get("responses") or {}).values():
        _visit_response(response, fn)
    for callback in (op.get("callbacks") or {}).values():
        if isinstance(callback, dict) and "$ref" not in callback:
            for path_item in callback.values():
                _visit_path_item(path_item, fn)
