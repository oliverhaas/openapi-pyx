"""Top-level generator orchestrator: spec path → generated package directory."""

from __future__ import annotations

from typing import TYPE_CHECKING

from openapi_pyx.codegen.emit_clients import emit_client_module
from openapi_pyx.codegen.emit_models import emit_models_module
from openapi_pyx.codegen.emit_root import emit_root_module
from openapi_pyx.codegen.format import format_directory
from openapi_pyx.codegen.render import render_module
from openapi_pyx.ingest.loader import load_spec
from openapi_pyx.naming import model_name, module_name
from openapi_pyx.transform.lowerer import lower_components
from openapi_pyx.transform.operations import build_document
from openapi_pyx.transform.resolver import build_schema_index

if TYPE_CHECKING:
    from pathlib import Path


def generate_client(spec_path: Path, out_dir: Path) -> None:
    """Generate a Python client package from an OpenAPI spec."""
    spec = load_spec(spec_path)
    index = build_schema_index(spec)
    schemas = lower_components(index)
    doc = build_document(spec, index, schemas)

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "models.py").write_text(render_module(emit_models_module(schemas)))

    if not doc.tags:
        (out_dir / "__init__.py").write_text(
            '"""Models-only package: the spec defined no operations under `paths`."""\n',
        )
        format_directory(out_dir)
        return

    (out_dir / "clients").mkdir(exist_ok=True)
    (out_dir / "client.py").write_text(render_module(emit_root_module(doc)))

    for tag in doc.tags:
        path = out_dir / "clients" / f"{module_name(tag.name)}.py"
        path.write_text(render_module(emit_client_module(tag)))

    (out_dir / "clients" / "__init__.py").write_text(
        "\n".join(
            f"from .{module_name(t.name)} import {model_name(t.name)}Client as {model_name(t.name)}Client"
            for t in doc.tags
        )
        + "\n",
    )
    (out_dir / "__init__.py").write_text('from .client import Client\n\n__all__ = ["Client"]\n')

    format_directory(out_dir)
