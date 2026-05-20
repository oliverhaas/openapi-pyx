# openapi-pyx

[![PyPI version](https://img.shields.io/pypi/v/openapi-pyx.svg?style=flat)](https://pypi.org/project/openapi-pyx/)
[![Python versions](https://img.shields.io/pypi/pyversions/openapi-pyx.svg)](https://pypi.org/project/openapi-pyx/)
[![CI](https://github.com/oliverhaas/openapi-pyx/actions/workflows/ci.yml/badge.svg)](https://github.com/oliverhaas/openapi-pyx/actions/workflows/ci.yml)

OpenAPI 3.1 → Python client generator. Pydantic v2 + httpx + async.

## Installation

```console
pip install openapi-pyx
```

## Usage

Generate a client from an OpenAPI 3.1 spec:

```console
openapi-pyx generate path/to/spec.yaml --out ./my_client
```

The output is a Python package with three layers:

- `my_client/models.py`: Pydantic v2 models, one per `components/schemas` entry
- `my_client/clients/<tag>.py`: one sub-client per OpenAPI tag, with one async method per operation
- `my_client/client.py`: top-level `Client` that wires sub-clients to a shared `httpx.AsyncClient`

Use it:

```python
import asyncio
from my_client import Client

async def main() -> None:
    async with Client(base_url="https://api.example.com") as client:
        pets = await client.pets.list_pets(limit=10)
        print(pets)

asyncio.run(main())
```

### v0.1 scope

- OpenAPI 3.1 only (3.0 rejected)
- Async client only (sync via `unasync` planned for v0.3)
- No auth helpers yet (planned for v0.2)
- No pagination, retries, or webhooks

## Documentation

Full documentation at [oliverhaas.github.io/openapi-pyx](https://oliverhaas.github.io/openapi-pyx/)

## License

MIT
