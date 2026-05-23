"""Normalized operation IR."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

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
class Operation:
    operation_id: str
    http_method: str  # "get", "post", "put", "patch", "delete"
    path: str
    summary: str | None
    description: str | None
    parameters: list[Parameter]
    request_body: RequestBody | None
    response: Response | None  # None when no 2xx body or only no-content responses
