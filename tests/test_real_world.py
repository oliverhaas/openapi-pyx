"""End-to-end tests against canonical OAI 3.1 example specs.

These are real, hand-written OpenAPI 3.1 specs from the OpenAPI Initiative,
vendored under `tests/fixtures/real/`. They exercise features that toy
fixtures miss: path-item-level parameter refs, schema-level `example`
fields, oauth security schemes, and webhook-only specs.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest

from openapi_pyx.generate import generate_client

if TYPE_CHECKING:
    from types import ModuleType

FIXTURES = Path(__file__).parent / "fixtures" / "real"


def _load_package(tmp_path: Path, spec: Path, package_name: str) -> ModuleType:
    out = tmp_path / package_name
    generate_client(spec, out)
    module_spec = importlib.util.spec_from_file_location(
        package_name,
        out / "__init__.py",
        submodule_search_locations=[str(out)],
    )
    assert module_spec is not None
    module = importlib.util.module_from_spec(module_spec)
    sys.modules[package_name] = module
    module_spec.loader.exec_module(module)
    return module


def test_tictactoe_generates_client_with_path_level_param_refs(tmp_path: Path):
    pkg = _load_package(tmp_path, FIXTURES / "tictactoe.yaml", "tictactoe_client")

    # Path-item-level $ref'd params (rowParam, columnParam) merge into operations.
    client = pkg.Client(base_url="https://api.example.com")
    assert hasattr(client, "gameplay")
    assert hasattr(client.gameplay, "get_board")
    assert hasattr(client.gameplay, "get_square")
    assert hasattr(client.gameplay, "put_square")

    from tictactoe_client import models  # noqa: PLC0415

    # Schemas are emitted under their PascalCased component names.
    assert hasattr(models, "Status")
    assert hasattr(models, "Mark")
    assert hasattr(models, "Coordinate")


@pytest.mark.asyncio
async def test_tictactoe_get_square_sends_path_params(tmp_path: Path):
    pkg = _load_package(tmp_path, FIXTURES / "tictactoe.yaml", "tictactoe_live_client")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/board/2/3"
        return httpx.Response(200, json="X")

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="https://api.example.com")
    async with pkg.Client(base_url="https://api.example.com", http=http) as client:
        mark = await client.gameplay.get_square(row=2, column=3)
    assert mark == "X"


def test_webhook_example_emits_models_only_package(tmp_path: Path):
    out = tmp_path / "webhook_pkg"
    generate_client(FIXTURES / "webhook-example.yaml", out)

    # No operations under `paths` → no Client, no clients/ directory.
    assert (out / "models.py").exists()
    assert (out / "__init__.py").exists()
    assert not (out / "client.py").exists()
    assert not (out / "clients").exists()

    pkg = _load_package(tmp_path, FIXTURES / "webhook-example.yaml", "webhook_models_pkg")
    assert not hasattr(pkg, "Client")
    from webhook_models_pkg import models  # noqa: PLC0415

    assert hasattr(models, "Pet")
