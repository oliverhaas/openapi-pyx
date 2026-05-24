"""Top-level generator orchestrator: spec path → generated package directory."""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING

from openapi_pyx.codegen.emit_clients import emit_client_module
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

    from openapi_pyx.codegen.nodes import Module
    from openapi_pyx.ir.document import TagGroup


_DATAMODEL_CODEGEN_FLAGS = (
    "--input-file-type",
    "openapi",
    "--output-model-type",
    "pydantic_v2.BaseModel",
    "--use-annotated",
    "--field-constraints",
    "--use-union-operator",
    "--use-standard-collections",
    "--target-python-version",
    "3.14",
    "--use-double-quotes",
    "--enum-field-as-literal",
    "all",
    "--disable-future-imports",
    "--disable-timestamp",
    "--use-type-alias",
    "--allow-population-by-field-name",
    "--formatters",
    "ruff-format",
    "ruff-check",
)


def generate_client(spec_path: Path, out_dir: Path) -> None:
    """Generate a Python client package from an OpenAPI spec."""
    spec = load_spec(spec_path)
    index = build_schema_index(spec)
    schemas = lower_components(index)
    doc = build_document(spec, index, schemas)

    out_dir.mkdir(parents=True, exist_ok=True)
    _run_datamodel_codegen(spec_path, out_dir / "models.py")

    if not doc.tags:
        (out_dir / "__init__.py").write_text(
            '"""Models-only package: the spec defined no operations under `paths`."""\n',
        )
        format_directory(out_dir)
        return

    (out_dir / "runtime.py").write_text(_RUNTIME_MODULE)
    (out_dir / "clients").mkdir(exist_ok=True)
    root_mod = emit_root_module(doc)
    (out_dir / "client.py").write_text(render_module(root_mod))

    tag_modules = [(tag, emit_client_module(tag)) for tag in doc.tags]
    for tag, mod in tag_modules:
        (out_dir / "clients" / f"{module_name(tag.name)}.py").write_text(render_module(mod))

    clients_init = (
        "\n".join(
            f"from .{module_name(t.name)} import {model_name(t.name)}Client as {model_name(t.name)}Client"
            for t in doc.tags
        )
        + "\n"
    )
    (out_dir / "clients" / "__init__.py").write_text(clients_init)

    # Sync tree: same IR, re-rendered with sync=True.
    _emit_sync_tree(out_dir, root_mod, tag_modules, clients_init)

    (out_dir / "__init__.py").write_text(
        "from ._sync.client import Client as SyncClient\n"
        "from .client import Client\n"
        "from .runtime import ApiError, Response\n\n"
        '__all__ = ["ApiError", "Client", "Response", "SyncClient"]\n',
    )

    format_directory(out_dir)


def _emit_sync_tree(
    out_dir: Path,
    root_mod: Module,
    tag_modules: list[tuple[TagGroup, Module]],
    clients_init: str,
) -> None:
    """Mirror `clients/` and `client.py` into `_sync/`, re-rendering each Module IR with sync=True."""
    sync_dir = out_dir / "_sync"
    (sync_dir / "clients").mkdir(parents=True, exist_ok=True)

    # Stub modules so relative imports inside the sync clients resolve.
    (sync_dir / "runtime.py").write_text(
        'from ..runtime import ApiError, Response\n\n__all__ = ["ApiError", "Response"]\n',
    )
    (sync_dir / "models.py").write_text("from ..models import *  # noqa: F403\n")
    (sync_dir / "__init__.py").write_text("")
    (sync_dir / "clients" / "__init__.py").write_text(clients_init)

    (sync_dir / "client.py").write_text(render_module(root_mod, sync=True))
    for tag, mod in tag_modules:
        (sync_dir / "clients" / f"{module_name(tag.name)}.py").write_text(render_module(mod, sync=True))


_RUNTIME_MODULE = '''\
"""Runtime helpers for the generated client. Hand-written, vendored on each codegen run."""

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class Response(Generic[T]):
    """Wrapper returned by `<op>_detailed(...)` methods, exposing the full HTTP response.

    `parsed` is a union over all documented response schemas (plus `None` for undocumented
    status codes or documented responses without a body).
    """

    status_code: int
    headers: dict[str, str]
    content: bytes
    parsed: T


class ApiError(Exception):
    """Raised by the simple-form (non-`_detailed`) methods on any non-2xx status code.

    `parsed` carries the validated error body if the status code matched a documented
    response schema; otherwise it is `None` and `content` holds the raw bytes.
    """

    def __init__(
        self,
        status_code: int,
        content: bytes,
        headers: dict[str, str],
        parsed: object | None = None,
    ) -> None:
        self.status_code = status_code
        self.content = content
        self.headers = dict(headers)
        self.parsed = parsed
        super().__init__(f"HTTP {status_code}")
'''


def _run_datamodel_codegen(spec_path: Path, out_path: Path) -> None:
    """Shell out to `datamodel-codegen` to emit Pydantic v2 models from the spec."""
    args = [
        sys.executable,
        "-m",
        "datamodel_code_generator",
        "--input",
        str(spec_path),
        "--output",
        str(out_path),
        *_DATAMODEL_CODEGEN_FLAGS,
    ]
    subprocess.run(args, check=True, capture_output=True, text=True)  # noqa: S603
