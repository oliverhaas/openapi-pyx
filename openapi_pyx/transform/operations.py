"""Walk paths/operations into normalized IR."""

from __future__ import annotations

from openapi_pydantic.v3.v3_1 import OpenAPI, Reference
from openapi_pydantic.v3.v3_1 import Operation as SpecOp
from openapi_pydantic.v3.v3_1 import Parameter as SpecParam
from openapi_pydantic.v3.v3_1 import RequestBody as SpecBody

from openapi_pyx.ir.document import Document, TagGroup
from openapi_pyx.ir.operation import Operation, Parameter, ParamLocation, RequestBody, Response
from openapi_pyx.ir.schema import NamedSchema  # noqa: TC001
from openapi_pyx.transform.lowerer import _lower  # internal use OK
from openapi_pyx.transform.resolver import SchemaIndex  # noqa: TC001

_HTTP_METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")
_DEFAULT_TAG = "default"


def build_document(spec: OpenAPI, index: SchemaIndex, schemas: list[NamedSchema]) -> Document:
    tags: dict[str, list[Operation]] = {}
    for path, item in (spec.paths or {}).items():
        for method in _HTTP_METHODS:
            spec_op: SpecOp | None = getattr(item, method, None)
            if spec_op is None:
                continue
            op = _build_operation(spec_op, path, method, index)
            for tag in spec_op.tags or [_DEFAULT_TAG]:
                tags.setdefault(tag, []).append(op)

    return Document(
        title=spec.info.title,
        schemas=schemas,
        tags=[TagGroup(name=name, operations=ops) for name, ops in sorted(tags.items())],
    )


def _build_operation(op: SpecOp, path: str, method: str, index: SchemaIndex) -> Operation:
    if not op.operationId:
        raise ValueError(f"Operation {method.upper()} {path} is missing operationId")

    return Operation(
        operation_id=op.operationId,
        http_method=method,
        path=path,
        summary=op.summary,
        parameters=[_build_param(p, index) for p in (op.parameters or [])],
        request_body=_build_body(op.requestBody, index),
        response=_build_response(op, index),
    )


def _build_param(param: SpecParam | Reference, index: SchemaIndex) -> Parameter:
    if isinstance(param, Reference):
        raise TypeError("$ref to parameters is not supported in v0.1")
    if param.param_in not in {"query", "path", "header"}:
        raise ValueError(f"Unsupported parameter location: {param.param_in}")
    if param.param_schema is None:
        raise ValueError(f"Parameter {param.name!r} is missing schema")
    return Parameter(
        name=param.name,
        location=ParamLocation(param.param_in),
        required=param.required if param.required is not None else (param.param_in == "path"),
        schema=_lower(param.param_schema, index),
        description=param.description,
    )


def _build_body(body: SpecBody | Reference | None, index: SchemaIndex) -> RequestBody | None:
    if body is None:
        return None
    if isinstance(body, Reference):
        raise TypeError("$ref to requestBodies is not supported in v0.1")
    media = (body.content or {}).get("application/json")
    if media is None or media.media_type_schema is None:
        return None
    return RequestBody(
        schema=_lower(media.media_type_schema, index),
        required=body.required if body.required is not None else False,
        content_type="application/json",
    )


def _build_response(op: SpecOp, index: SchemaIndex) -> Response | None:
    if not op.responses:
        return None
    # Pick the first 2xx with application/json content. OpenAPI 3.1 also
    # allows wildcards like "2XX", so match both fixed 2xx codes and the
    # wildcard form.
    for status, resp in op.responses.items():
        if not _is_2xx(status):
            continue
        if isinstance(resp, Reference):
            continue
        media = (resp.content or {}).get("application/json")
        if media is None or media.media_type_schema is None:
            continue
        return Response(
            schema=_lower(media.media_type_schema, index),
            content_type="application/json",
        )
    return None


_STATUS_CODE_LENGTH = 3


def _is_2xx(status: str) -> bool:
    if status.upper() == "2XX":
        return True
    return len(status) == _STATUS_CODE_LENGTH and status[0] == "2" and status[1:].isdigit()
