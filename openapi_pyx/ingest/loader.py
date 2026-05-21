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

    _strip_examples(raw)

    try:
        return OpenAPI.model_validate(raw)
    except Exception as exc:
        raise LoadError(f"Spec failed validation: {exc}") from exc


def _strip_examples(node: Any) -> None:  # noqa: ANN401
    """Drop `example` and `examples` fields recursively.

    They're documentation only, and their `$ref`s into `#/components/examples/`
    would otherwise need separate handling we don't care about for codegen.
    """
    if isinstance(node, dict):
        node.pop("example", None)
        node.pop("examples", None)
        for v in node.values():
            _strip_examples(v)
    elif isinstance(node, list):
        for item in node:
            _strip_examples(item)
