"""Load and validate an OpenAPI 3.1 spec into openapi-pydantic models."""

from __future__ import annotations

import json
from pathlib import Path  # noqa: TC003
from typing import Any

import yaml
from openapi_pydantic.v3.v3_1 import OpenAPI


class LoadError(ValueError):
    """Raised when a spec cannot be loaded or fails 3.1 validation."""


def load_spec(path: Path) -> OpenAPI:
    """Load an OpenAPI 3.1 spec from a YAML or JSON file."""
    text = path.read_text(encoding="utf-8")
    raw = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)

    if not isinstance(raw, dict):
        raise LoadError(f"Spec at {path} is not a mapping")

    version = raw.get("openapi", "")
    if not isinstance(version, str) or not version.startswith("3.1"):
        raise LoadError(f"Only OpenAPI 3.1 is supported; got openapi={version!r}")

    _strip_example_refs(raw)
    components = raw.get("components")
    if isinstance(components, dict):
        components.pop("examples", None)

    try:
        return OpenAPI.model_validate(raw)
    except Exception as exc:
        raise LoadError(f"Spec failed validation: {exc}") from exc


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
