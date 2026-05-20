# openapi-pyx

OpenAPI 3.1 → Python client generator. Pydantic v2 + httpx + async.

## Quick Start

Generate a type-safe, async Python client from your OpenAPI 3.1 specification:

```console
openapi-pyx generate path/to/spec.yaml --out ./my_client
```

The generated client includes:

- **models.py**: Pydantic v2 models for all `components/schemas`
- **clients/<tag>.py**: one sub-client per OpenAPI tag, fully typed
- **client.py**: top-level `Client` class with automatic session management

## Usage Example

```python
import asyncio
from my_client import Client

async def main() -> None:
    async with Client(base_url="https://api.example.com") as client:
        pets = await client.pets.list_pets(limit=10)
        print(pets)

asyncio.run(main())
```

## v0.1 Capabilities

- **OpenAPI 3.1** spec generation (3.0 not supported)
- **Async-only** client (sync support planned for v0.3 via `unasync`)
- **Pydantic v2** models with full validation
- **httpx** for HTTP, with built-in `AsyncClient` lifecycle
- **No auth helpers** yet (v0.2 roadmap)
- **No pagination, retries, or webhooks** (future versions)
