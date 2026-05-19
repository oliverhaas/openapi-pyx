# openapi-pyx

OpenAPI 3.1 → Python client generator. Pydantic v2 + httpx + async. Code-generation (offline, commit output).

Working title. Real name TBD.

## Problem

Every existing Python OpenAPI client generator falls down on at least one of:

- **Broken Pydantic models** -- missing fields, wrong types on `oneOf`/discriminators, mis-handled nullable arrays, recursive refs that crash or silently produce `Any`, generated models that fail validation on the actual API responses they're supposed to describe.
- **Spec edge cases ignored** -- crashes or silent skips on `oneOf`/`anyOf`/`allOf`, `$ref` chains, `additionalProperties`, nullable arrays, recursive schemas, discriminated unions without `propertyName`.
- **Ugly, unergonomic output** -- generated code that screams "generated": bad naming, no real type annotations (lots of `Any`), no idiomatic httpx, awkward call patterns, fat clients that hurt IDE autocomplete.

The combination of "actually correct Pydantic v2 models for arbitrary 3.1 specs" + "idiomatic async httpx client" + "code you'd be happy writing by hand" does not exist in the Python ecosystem.

## Scope

MVP:

- **OpenAPI 3.1 only** -- rejects 3.0. 3.1's schemas align with JSON Schema 2020-12, which is what Pydantic v2 speaks natively. Most existing tools spend half their code massaging 3.0 quirks (`nullable: true`, exclusive bounds, etc.) and accumulate bugs in the process.
- **Pydantic v2 native** -- `Annotated[...]`-heavy types, `TypeAdapter` where appropriate, `Discriminator`/`Tag` for discriminated unions, native union handling. No `from __future__ import annotations` workarounds for things Pydantic v2 already does.
- **httpx + async only** -- one HTTP client, one execution model. Sync derived via `unasync` later (same approach httpx itself uses for its sync surface).
- **Tagged sub-clients** -- `client.pets.list_pets(...)`. Group methods by OpenAPI tag; one sub-client per tag plus a top-level `Client` that wires them together. Good IDE autocomplete; mirrors how docs are organized.
- **Thin call methods** -- each generated method does: build request → send → parse response into Pydantic model. No magic.
- **Real types end-to-end** -- request params, request body, response body all typed; no `dict[str, Any]` escape hatches except where the spec genuinely allows free-form.
- **Formatted output** -- post-process with `ruff format` and `ruff check --fix`. Generated code passes the same linter the user runs.

Out of scope for MVP (deferred):

- OpenAPI 3.0 / Swagger 2.0
- Sync client (later, via `unasync`)
- Auth helpers from `securitySchemes`
- Pagination iterator detection
- Built-in retries / rate-limiting / backoff
- Webhooks, callbacks
- Server stub generation

## Pipeline

1. **Parse + validate** spec into a typed internal IR (likely built on `openapi-pydantic` or similar).
2. **Resolve `$ref`s** and normalize schemas: collapse `allOf`, flatten transparent indirection, mark recursive refs.
3. **Lower to Pydantic-friendly shapes** -- `oneOf` with `discriminator` → `Annotated[Union[...], Discriminator(...)]`; `oneOf` without → tagged union via `model_validator`; `allOf` → composed model with inherited fields.
4. **Emit models** -- one type per schema component, deterministic ordering for stable diffs.
5. **Emit per-tag sub-clients** -- async methods with typed params, body, and return.
6. **Emit composed `Client`** -- wires sub-clients to a shared `httpx.AsyncClient`.
7. **Format** -- `ruff format` + `ruff check --fix --select I` (import sorting).

## Phased roadmap

- **v0.1**: models + sub-client methods, async-only, no auth
- **v0.2**: auth helpers from `securitySchemes` (bearer, basic, API key, OAuth2 client-credentials)
- **v0.3**: sync client via `unasync`
- **v0.4**: pagination iterator detection (cursor, offset, Link header)
- **v0.5**: retries / backoff

## Prior art

What to study and selectively borrow from:

- **openapi-python-client** -- closest in shape (sub-clients, httpx async, Pydantic). Borrow: project layout, httpx-Async integration patterns. Gaps: model fidelity on complex specs, output aesthetics, hasn't fully embraced Pydantic v2 idioms.
- **datamodel-code-generator** -- the most-used Pydantic model generator. Borrow: model emission idioms, large library of edge cases. Gaps: model-only (no client), flaky on some 3.1 features, output style is dated.
- **openapi-pydantic** -- typed parser for OpenAPI specs. Possible direct dependency for spec ingestion.
- **unasync** (python-trio) -- the tool httpx uses to derive sync from async source. Same approach here for v0.3.
- **openapi-generator** (Java) -- generic generator with Python templates. Output is ugly but the project's issue tracker is a goldmine of real-world spec edge cases to test against.
- **Speakeasy**, **Fern**, **Stainless** (mostly TypeScript-world but also Python) -- commercial SDK generators. Output aesthetics are state-of-the-art; worth studying for what "code you'd be happy to write by hand" looks like.
- **bravado**, **pyswagger** -- older / less maintained. Mostly historical; runtime-dispatch model rather than code-gen.

## Notes

- Test suite is the differentiator: a corpus of real-world specs (Stripe, GitHub, OpenAI, Slack, Linear, etc.) plus the standard OpenAPI test suite plus a curated set of edge-case minispecs (every `oneOf` shape, every recursive-ref shape, every nullable-array shape). For each spec, golden-file the output and round-trip real example payloads through the generated models to confirm they validate.
- Elevator pitch: "What if an OpenAPI-3.1 generator actually used Pydantic v2 the way Pydantic v2 wants to be used, and produced code you'd be happy writing by hand?"
- Open question: how much of the parse/IR layer can be reused from `openapi-pydantic` vs. needing a custom typed model. Worth a spike before committing to either.
- Open question: code-gen via Jinja templates (most generators) vs. AST construction (`ast.unparse`). Templates are easier to author; AST is easier to keep correct across Python versions. Probably Jinja for v0.1.
