"""Normalized operation IR."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from openapi_pyx.ir.schema import Schema  # noqa: TC001


class ParamLocation(Enum):
    QUERY = "query"
    PATH = "path"
    HEADER = "header"


@dataclass(frozen=True, slots=True)
class Parameter:
    name: str
    location: ParamLocation
    required: bool
    schema: Schema
    description: str | None = None
    examples: list[Any] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RequestBody:
    schema: Schema
    required: bool
    content_type: str  # always "application/json" in v0.1


@dataclass(frozen=True, slots=True)
class Response:
    schema: Schema
    content_type: str  # always "application/json" in v0.1


@dataclass(frozen=True, slots=True)
class ResponseBranch:
    """One documented status-code → schema mapping. `schema` is None for responses without a body."""

    status_code: str  # exact ("200"), wildcard ("2XX", "4XX"), or "default"
    schema: Schema | None


@dataclass(frozen=True, slots=True)
class Operation:
    operation_id: str
    http_method: str  # "get", "post", "put", "patch", "delete"
    path: str
    summary: str | None
    description: str | None
    parameters: list[Parameter]
    request_body: RequestBody | None
    response: Response | None  # The 2xx body returned by the simple variant. None means no documented 2xx body.
    branches: list[ResponseBranch] = field(default_factory=list)  # All documented responses for the detailed variant.
