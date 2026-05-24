"""Load and validate an OpenAPI 3.0 or 3.1 spec into openapi-pydantic models."""

from __future__ import annotations

import json
import re
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
    run regardless of input version: YAML int response keys are stringified, ref-only
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

    _strip_example_refs(raw)
    _inline_schema_aliases(raw)
    _strip_unsupported_patterns(raw)
    components = raw.get("components")
    if isinstance(components, dict):
        components.pop("examples", None)
    return raw


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
    """
    if isinstance(node, dict):
        # OpenAPI Examples Object: dict-shaped `examples`. JSON Schema: list-shaped.
        if isinstance(node.get("examples"), dict):
            node.pop("examples", None)
        # GitHub's spec uses `example: {$ref: "#/components/examples/..."}` in places.
        # That's a ref disguised as a literal; drop it.
        example_value = node.get("example")
        if isinstance(example_value, dict) and "$ref" in example_value:
            node.pop("example", None)
        for v in node.values():
            _strip_example_refs(v)
    elif isinstance(node, list):
        for item in node:
            _strip_example_refs(item)
