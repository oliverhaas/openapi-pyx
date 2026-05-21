# Changelog

## 0.1.0a1 (Unreleased)

Initial alpha release.

### Pipeline

- OpenAPI 3.1 spec ingest via `openapi-pydantic` (YAML and JSON)
- `$ref` resolution with Tarjan SCC for recursion detection
- Schema normalization: `allOf` composition, `oneOf`/`anyOf` lowering,
  `2XX` wildcard responses

### Generated client

- Pydantic v2 models for every `components/schemas` entry
- Discriminated unions via `Annotated[..., Discriminator(...)]` and `Tag(...)`
- Recursive types via string forward refs (no `from __future__ import annotations`)
- Per-tag sub-clients, each with one async method per operation
- Top-level `Client` with `httpx.AsyncClient` lifecycle and async context manager
- Identifier sanitization for Python keywords and builtins
- Fields with sanitized names use `Field(alias=...)` + `populate_by_name=True`
  so both the wire name and the Python name validate
- Output formatted with `ruff format` + `ruff check --fix --select I,F401`

### Out of scope for this release

- Auth helpers from `securitySchemes` (planned for v0.2)
- Sync client via `unasync` (planned for v0.3)
- Pagination iterators, retries, webhooks
