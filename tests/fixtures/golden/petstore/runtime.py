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
