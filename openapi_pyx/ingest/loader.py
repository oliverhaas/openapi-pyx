"""Load and validate an OpenAPI 3.0 or 3.1 spec into openapi-pydantic models."""

from __future__ import annotations

import copy
import json
import re
import urllib.parse
from pathlib import Path  # noqa: TC003
from typing import Any

import yaml
from openapi_pydantic.v3.v3_1 import OpenAPI

from openapi_pyx.ingest._convert_3_0 import convert_3_0_to_3_1


class LoadError(ValueError):
    """Raised when a spec cannot be loaded or fails validation."""


def load_spec(path: Path) -> OpenAPI:
    """Load and validate an OpenAPI 3.0 or 3.1 spec."""
    raw = load_normalized_raw(path)
    try:
        return OpenAPI.model_validate(raw)
    except Exception as exc:
        raise LoadError(f"Spec failed validation: {exc}") from exc


def load_normalized_raw(path: Path) -> dict[str, Any]:
    """Load the spec as a v3.1-shaped dict, applying every load-time normalization.

    3.0 specs go through a typed conversion (parse as `v3_0.OpenAPI`, walk and convert
    each Schema, emit as 3.1-shaped dict). Then a few orthogonal raw-dict workarounds
    run regardless of input version: YAML int response keys are stringified, vendor
    extensions (`x-*`) are dropped, cross-path `$ref` pointers are inlined, ref-only
    schema aliases are inlined, `pattern` fields that pydantic-core can't compile are
    dropped, OpenAPI Examples Objects (the named-map kind) are stripped. The returned
    dict is also fed to `datamodel-codegen` so it sees the same normalizations as our
    pipeline does.
    """
    text = path.read_text(encoding="utf-8")
    raw = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)

    if not isinstance(raw, dict):
        raise LoadError(f"Spec at {path} is not a mapping")

    version = raw.get("openapi", "")
    if not isinstance(version, str):
        raise LoadError(f"Spec has non-string `openapi` field: {version!r}")

    # Stringify before any typed parse; v3.0/v3.1 models reject int response keys.
    _stringify_response_keys(raw)

    if version.startswith("3.0"):
        try:
            raw = convert_3_0_to_3_1(raw)
        except Exception as exc:
            raise LoadError(f"3.0 spec failed structural validation: {exc}") from exc
    elif not version.startswith("3.1"):
        raise LoadError(f"Only OpenAPI 3.0 and 3.1 are supported; got openapi={version!r}")

    _strip_vendor_extensions(raw)
    _strip_example_refs(raw)
    _inline_unsupported_refs(raw)
    _inline_schema_aliases(raw)
    _strip_unsupported_patterns(raw)
    components = raw.get("components")
    if isinstance(components, dict):
        components.pop("examples", None)
    return raw


def _strip_vendor_extensions(node: Any) -> None:  # noqa: ANN401
    """Recursively drop `x-*` keys. They're documentation/tooling hints with no impact on
    the generated client, and Scayle has `$ref`s pointing inside `x-codeSamples` strings
    that our `#/components/...`-only resolver can't validate.
    """
    if isinstance(node, dict):
        for key in [k for k in node if isinstance(k, str) and k.startswith("x-")]:
            node.pop(key)
        for v in node.values():
            _strip_vendor_extensions(v)
    elif isinstance(node, list):
        for item in node:
            _strip_vendor_extensions(item)


def _stringify_response_keys(node: Any) -> None:  # noqa: ANN401
    """Recursively rewrite `responses: {200: ...}` (YAML int) to `responses: {"200": ...}`."""
    if isinstance(node, dict):
        responses = node.get("responses")
        if isinstance(responses, dict) and not all(isinstance(k, str) for k in responses):
            node["responses"] = {str(k): v for k, v in responses.items()}
        for v in node.values():
            _stringify_response_keys(v)
    elif isinstance(node, list):
        for item in node:
            _stringify_response_keys(item)


_CANONICAL_REF_PREFIXES = (
    "#/components/schemas/",
    "#/components/parameters/",
    "#/components/requestBodies/",
    "#/components/responses/",
    "#/components/headers/",
)


_MAX_INLINE_DEPTH = 16


def _is_canonical_ref(ref: str) -> bool:
    """A canonical ref is one of our supported component sections plus a single name segment."""
    return any(ref.startswith(prefix) and "/" not in ref.removeprefix(prefix) for prefix in _CANONICAL_REF_PREFIXES)


def _inline_unsupported_refs(raw: dict[str, Any]) -> None:
    """Inline any `$ref` that doesn't point at a canonical top-level component.

    Real-world 3.0 specs (Scayle) use cross-path refs (`#/paths/...`) to dedup
    boilerplate responses/parameters, and deep JSON Pointers into `components.schemas`
    (`#/components/schemas/<Name>/properties/<x>/allOf/0`) to share inline sub-schemas.
    Our resolver only supports single-segment component refs, so we resolve and inline
    everything else at load time.
    """
    _walk_inline_refs(raw, raw, depth=0)


def _walk_inline_refs(root: dict[str, Any], node: Any, *, depth: int) -> None:  # noqa: ANN401
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and not _is_canonical_ref(ref) and depth < _MAX_INLINE_DEPTH:
            target = _resolve_json_pointer(root, ref)
            if isinstance(target, dict):
                node.clear()
                node.update(copy.deepcopy(target))
                _walk_inline_refs(root, node, depth=depth + 1)
                return
        for v in node.values():
            _walk_inline_refs(root, v, depth=depth)
    elif isinstance(node, list):
        for item in node:
            _walk_inline_refs(root, item, depth=depth)


def _resolve_json_pointer(root: dict[str, Any], pointer: str) -> Any:  # noqa: ANN401
    """Resolve an RFC 6901 JSON Pointer (with URL-encoded path segments) against `root`.

    Returns `None` if any segment doesn't resolve; callers leave the original `$ref`
    in place so downstream validation surfaces a clearer error.
    """
    if not pointer.startswith("#/"):
        return None
    cur: Any = root
    for raw_part in pointer[2:].split("/"):
        part = urllib.parse.unquote(raw_part).replace("~1", "/").replace("~0", "~")
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and 0 <= int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


_COMPONENT_SCHEMA_PREFIX = "#/components/schemas/"


def _inline_schema_aliases(raw: dict[str, Any]) -> None:
    """Replace ref-only entries under `components.schemas` with the target schema's content.

    Real-world 3.0 specs (Asana, others) commonly define `Foo: {$ref: '#/components/schemas/Bar'}`
    aliases at the top level. We follow each chain to its concrete schema and substitute,
    leaving Foo and Bar as independent copies of the same content. Both names remain usable
    as references elsewhere in the spec.
    """
    components = raw.get("components")
    if not isinstance(components, dict):
        return
    schemas = components.get("schemas")
    if not isinstance(schemas, dict):
        return
    for name in list(schemas):
        if not isinstance(name, str):
            continue
        target = _follow_schema_alias(schemas, name)
        if target is not None and target != name:
            schemas[name] = schemas[target]


def _follow_schema_alias(schemas: dict[str, Any], start: str) -> str | None:
    seen: set[str] = set()
    cur = start
    while True:
        entry = schemas.get(cur)
        if not isinstance(entry, dict):
            return None
        ref = entry.get("$ref")
        if not isinstance(ref, str) or not ref.startswith(_COMPONENT_SCHEMA_PREFIX):
            return cur
        if any(k for k in entry if k != "$ref"):
            return cur  # has other content; not a pure alias
        target = ref.removeprefix(_COMPONENT_SCHEMA_PREFIX)
        if target in seen:
            return None  # cycle
        seen.add(target)
        cur = target


_BACKREF_RE = re.compile(r"\\[1-9]")


def _strip_unsupported_patterns(node: Any) -> None:  # noqa: ANN401
    """Drop `pattern` fields whose regex relies on features pydantic-core can't compile.

    pydantic-core uses Rust's `regex` crate, which doesn't support backreferences
    (e.g. Asana has `(...)(,\\1)*`). We strip the offending entries so validation
    doesn't blow up at import time. The semantic effect is that we don't enforce
    the regex at runtime, which is the same as having no pattern in the first place.
    """
    if isinstance(node, dict):
        pattern = node.get("pattern")
        if isinstance(pattern, str) and _BACKREF_RE.search(pattern):
            node.pop("pattern", None)
        for v in node.values():
            _strip_unsupported_patterns(v)
    elif isinstance(node, list):
        for item in node:
            _strip_unsupported_patterns(item)


def _strip_example_refs(node: Any) -> None:  # noqa: ANN401
    """Drop OpenAPI Examples Objects but keep JSON Schema 2020-12 examples.

    Both fields are called `examples`, but the shapes differ. JSON Schema's
    `examples` is a list of inline values (useful for `Field(examples=...)`).
    OpenAPI's Examples Object is a `{name: ExampleObject|$ref}` map pointing
    at `#/components/examples/...`, which we don't resolve. The
    `components.examples` section is the ref target pool, so drop that too.

    We also drop `example` / `examples` whose values transitively reference
    `#/components/examples/...`. Scayle nests these as `example: {<name>: {$ref: ...}}`,
    which is not standard OpenAPI but appears in real specs.
    """
    if isinstance(node, dict):
        # OpenAPI Examples Object: dict-shaped `examples`. JSON Schema: list-shaped.
        if isinstance(node.get("examples"), dict):
            node.pop("examples", None)
        # GitHub uses `example: {$ref: "#/components/examples/..."}`; Scayle nests one
        # level deeper as `example: {<name>: {$ref: ...}}`. Either way the field is
        # informational and would dangle after we drop `components.examples`.
        if _has_components_example_ref(node.get("example")):
            node.pop("example", None)
        for v in node.values():
            _strip_example_refs(v)
    elif isinstance(node, list):
        for item in node:
            _strip_example_refs(item)


def _has_components_example_ref(value: Any) -> bool:  # noqa: ANN401
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/examples/"):
            return True
        return any(_has_components_example_ref(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_components_example_ref(v) for v in value)
    return False
