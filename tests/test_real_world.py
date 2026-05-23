"""End-to-end tests against real-world OpenAPI 3.1 specs.

The OAI canonical examples (tic-tac-toe, webhook-example) are vendored
under `tests/fixtures/real/` and exercise path-item-level parameter refs,
inline schema examples, oauth security schemes, and webhook-only specs.

The GitHub REST API description is much larger (~9.5 MB) and stresses
operation-id sanitization, inline discriminator branches, embedded quotes
in docstrings, and Pydantic's leading-underscore rule. It's downloaded
on demand and only runs when `OPENAPI_PYX_TEST_GITHUB=1` is set.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest

from openapi_pyx.generate import generate_client

if TYPE_CHECKING:
    from types import ModuleType

FIXTURES = Path(__file__).parent / "fixtures" / "real"
GITHUB_SPEC_URL = (
    "https://raw.githubusercontent.com/github/rest-api-description/main/"
    "descriptions-next/api.github.com/api.github.com.yaml"
)
EXPECTED_GITHUB_MIN_MODELS = 800
EXPECTED_GITHUB_MIN_SUB_CLIENTS = 40


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


def test_tictactoe_method_docstring_includes_summary_and_description(tmp_path: Path):
    pkg = _load_package(tmp_path, FIXTURES / "tictactoe.yaml", "tictactoe_doc_client")

    client = pkg.Client(base_url="https://api.example.com")
    get_board = client.gameplay.get_board
    assert get_board.__doc__ is not None
    assert "Get the whole board" in get_board.__doc__  # summary
    assert "Retrieves the current state of the board" in get_board.__doc__  # description

    # Parameter descriptions land in the Args: block.
    get_square = client.gameplay.get_square
    assert get_square.__doc__ is not None
    assert "Args:" in get_square.__doc__
    assert "row: Board row (vertical coordinate)" in get_square.__doc__
    assert "column: Board column (horizontal coordinate)" in get_square.__doc__


def test_tictactoe_aliases_carry_description_and_enum_constraints(tmp_path: Path):
    pkg = _load_package(tmp_path, FIXTURES / "tictactoe.yaml", "tictactoe_alias_client")
    from tictactoe_alias_client import models  # noqa: PLC0415

    # `Mark` is `class Mark(RootModel[Literal[...]])`; `__doc__` carries the spec description.
    assert models.Mark.__doc__ is not None
    assert "board square" in models.Mark.__doc__.lower()

    # Numeric constraints on `coordinate` (`minimum: 1, maximum: 3`) reach Pydantic via Field args.
    schema = models.Coordinate.model_json_schema()
    assert schema["minimum"] == 1
    assert schema["maximum"] == 3
    assert schema["examples"] == [1]

    # `Mark.model_validate(value)` enforces the Literal enum at runtime.
    assert models.Mark.model_validate("X").root == "X"


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
    # `Mark` is a `RootModel[Literal[...]]` so the wire value is unwrapped via `.root`.
    assert mark.root == "X"


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


@pytest.mark.skipif(
    os.environ.get("OPENAPI_PYX_TEST_GITHUB") != "1",
    reason="Set OPENAPI_PYX_TEST_GITHUB=1 to enable; downloads the ~9.5 MB GitHub REST API spec.",
)
def test_github_rest_api_spec_generates_and_imports(tmp_path: Path):
    """End-to-end: download GitHub's REST API spec and generate a working client.

    Stresses operation-id slashes, inline discriminator oneOf branches, embedded
    quotes in descriptions, and Pydantic's leading-underscore field restriction.
    """
    spec_path = tmp_path / "github-api.yaml"
    urllib.request.urlretrieve(GITHUB_SPEC_URL, spec_path)  # noqa: S310

    pkg = _load_package(tmp_path, spec_path, "github_client_e2e")

    client = pkg.Client(base_url="https://api.github.com")
    sub_clients = [a for a in dir(client) if not a.startswith("_")]
    assert len(sub_clients) >= EXPECTED_GITHUB_MIN_SUB_CLIENTS

    from github_client_e2e import models  # noqa: PLC0415

    model_names = [n for n in dir(models) if not n.startswith("_") and n[:1].isupper()]
    assert len(model_names) >= EXPECTED_GITHUB_MIN_MODELS
