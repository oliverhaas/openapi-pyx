import importlib.util
import sys
from pathlib import Path

import httpx
import pytest

from openapi_pyx.generate import generate_client

FIXTURES = Path(__file__).parent / "fixtures"


def _load_client(tmp_path: Path):
    out = tmp_path / "live_client"
    generate_client(FIXTURES / "petstore.yaml", out)
    spec = importlib.util.spec_from_file_location(
        "live_client",
        out / "__init__.py",
        submodule_search_locations=[str(out)],
    )
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["live_client"] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_list_pets_sends_limit_query_and_parses_response(tmp_path: Path):
    pkg = _load_client(tmp_path)

    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=[{"id": 1, "name": "Rex"}])

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="https://api.example.com")
    client = pkg.Client(base_url="https://api.example.com", http=http)
    async with client:
        pets = await client.pets.list_pets(limit=5)
    assert seen[0].url.path == "/pets"
    assert dict(seen[0].url.params) == {"limit": "5"}
    assert pets[0].name == "Rex"


@pytest.mark.asyncio
async def test_show_pet_by_id_uses_path_segment(tmp_path: Path):
    pkg = _load_client(tmp_path)

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/pets/abc"
        return httpx.Response(200, json={"id": 42, "name": "Rex"})

    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="https://api.example.com")
    client = pkg.Client(base_url="https://api.example.com", http=http)
    async with client:
        pet = await client.pets.show_pet_by_id(pet_id="abc")
    assert pet.id == 42
