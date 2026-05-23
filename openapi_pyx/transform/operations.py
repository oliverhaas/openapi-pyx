"""Walk paths/operations into normalized IR."""

from __future__ import annotations

from openapi_pydantic.v3.v3_1 import OpenAPI, Reference
from openapi_pydantic.v3.v3_1 import Operation as SpecOp
from openapi_pydantic.v3.v3_1 import Parameter as SpecParam
from openapi_pydantic.v3.v3_1 import RequestBody as SpecBody
from openapi_pydantic.v3.v3_1 import Response as SpecResponse

from openapi_pyx.ir.document import Document, TagGroup
from openapi_pyx.ir.operation import Operation, Parameter, ParamLocation, RequestBody, Response
from openapi_pyx.ir.schema import NamedSchema, NamedSchemaRef
from openapi_pyx.transform.lowerer import _examples_of, _lower  # internal use OK
from openapi_pyx.transform.resolver import SchemaIndex  # noqa: TC001

_HTTP_METHODS = ("get", "put", "post", "delete", "patch", "head", "options", "trace")
_DEFAULT_TAG = "default"

_PARAM_PREFIX = "#/components/parameters/"
_BODY_PREFIX = "#/components/requestBodies/"
_RESPONSE_PREFIX = "#/components/responses/"


def build_document(spec: OpenAPI, index: SchemaIndex, schemas: list[NamedSchema]) -> Document:
    by_name = {ns.name: ns for ns in schemas}
    tags: dict[str, list[Operation]] = {}
    for path, item in (spec.paths or {}).items():
        path_params = item.parameters or []
        for method in _HTTP_METHODS:
            spec_op: SpecOp | None = getattr(item, method, None)
            if spec_op is None:
                continue
            op = _build_operation(spec_op, path, method, index, spec, path_params, by_name)
            for tag in spec_op.tags or [_DEFAULT_TAG]:
                tags.setdefault(tag, []).append(op)

    return Document(
        title=spec.info.title,
        schemas=schemas,
        tags=[TagGroup(name=name, operations=ops) for name, ops in sorted(tags.items())],
    )


def _build_operation(  # noqa: PLR0913
    op: SpecOp,
    path: str,
    method: str,
    index: SchemaIndex,
    spec: OpenAPI,
    path_params: list[SpecParam | Reference],
    by_name: dict[str, NamedSchema],
) -> Operation:
    if not op.operationId:
        raise ValueError(f"Operation {method.upper()} {path} is missing operationId")

    merged = _merge_params(path_params, op.parameters or [], spec)

    return Operation(
        operation_id=op.operationId,
        http_method=method,
        path=path,
        summary=op.summary,
        description=op.description,
        parameters=[_build_param(p, index, by_name) for p in merged],
        request_body=_build_body(op.requestBody, index, spec),
        response=_build_response(op, index, spec),
    )


def _merge_params(
    path_params: list[SpecParam | Reference],
    op_params: list[SpecParam | Reference],
    spec: OpenAPI,
) -> list[SpecParam]:
    """Merge path-item-level parameters with operation-level. Operation overrides path on (name, in)."""
    by_key: dict[tuple[str, str], SpecParam] = {}
    for p in path_params:
        resolved = _resolve_parameter(p, spec)
        by_key[(resolved.name, resolved.param_in)] = resolved
    for p in op_params:
        resolved = _resolve_parameter(p, spec)
        by_key[(resolved.name, resolved.param_in)] = resolved
    return list(by_key.values())


def _build_param(param: SpecParam, index: SchemaIndex, by_name: dict[str, NamedSchema]) -> Parameter:
    if param.param_in not in {"query", "path", "header"}:
        raise ValueError(f"Unsupported parameter location: {param.param_in}")
    if param.param_schema is None:
        raise ValueError(f"Parameter {param.name!r} is missing schema")
    lowered = _lower(param.param_schema, index)
    return Parameter(
        name=param.name,
        location=ParamLocation(param.param_in),
        required=param.required if param.required is not None else (param.param_in == "path"),
        schema=lowered,
        description=param.description,
        examples=_param_examples(param, lowered, by_name),
    )


def _param_examples(
    param: SpecParam,
    lowered: object,
    by_name: dict[str, NamedSchema],
) -> list[object]:
    if param.example is not None:
        return [param.example]
    schema = param.param_schema
    if schema is not None and not isinstance(schema, Reference):
        examples = _examples_of(schema)
        if examples:
            return examples
    # Follow one level of $ref into the lowered NamedSchema so e.g. tic-tac-toe's
    # `row` parameter picks up `Coordinate.examples = [1]`.
    if isinstance(lowered, NamedSchemaRef):
        target = by_name.get(lowered.name)
        if target is not None:
            return list(target.examples)
    return []


def _build_body(body: SpecBody | Reference | None, index: SchemaIndex, spec: OpenAPI) -> RequestBody | None:
    if body is None:
        return None
    body = _resolve_request_body(body, spec)
    media = (body.content or {}).get("application/json")
    if media is None or media.media_type_schema is None:
        return None
    return RequestBody(
        schema=_lower(media.media_type_schema, index),
        required=body.required if body.required is not None else False,
        content_type="application/json",
    )


def _build_response(op: SpecOp, index: SchemaIndex, spec: OpenAPI) -> Response | None:
    if not op.responses:
        return None
    for status, resp in op.responses.items():
        if not _is_2xx(status):
            continue
        resolved = _resolve_response(resp, spec)
        media = (resolved.content or {}).get("application/json")
        if media is None or media.media_type_schema is None:
            continue
        return Response(
            schema=_lower(media.media_type_schema, index),
            content_type="application/json",
        )
    return None


def _resolve_parameter(param: SpecParam | Reference, spec: OpenAPI) -> SpecParam:
    if not isinstance(param, Reference):
        return param
    name = _ref_name(param.ref, _PARAM_PREFIX)
    components = spec.components
    if components is None or not components.parameters:
        raise ValueError(f"Parameter ref {param.ref!r} not resolvable: no components.parameters")
    target = components.parameters.get(name)
    if target is None:
        raise ValueError(f"Parameter ref not found: {param.ref!r}")
    if isinstance(target, Reference):
        raise TypeError(f"Chained parameter refs are not supported: {param.ref!r}")
    return target


def _resolve_request_body(body: SpecBody | Reference, spec: OpenAPI) -> SpecBody:
    if not isinstance(body, Reference):
        return body
    name = _ref_name(body.ref, _BODY_PREFIX)
    components = spec.components
    if components is None or not components.requestBodies:
        raise ValueError(f"RequestBody ref {body.ref!r} not resolvable: no components.requestBodies")
    target = components.requestBodies.get(name)
    if target is None:
        raise ValueError(f"RequestBody ref not found: {body.ref!r}")
    if isinstance(target, Reference):
        raise TypeError(f"Chained requestBody refs are not supported: {body.ref!r}")
    return target


def _resolve_response(resp: SpecResponse | Reference, spec: OpenAPI) -> SpecResponse:
    if not isinstance(resp, Reference):
        return resp
    name = _ref_name(resp.ref, _RESPONSE_PREFIX)
    components = spec.components
    if components is None or not components.responses:
        raise ValueError(f"Response ref {resp.ref!r} not resolvable: no components.responses")
    target = components.responses.get(name)
    if target is None:
        raise ValueError(f"Response ref not found: {resp.ref!r}")
    if isinstance(target, Reference):
        raise TypeError(f"Chained response refs are not supported: {resp.ref!r}")
    return target


def _ref_name(ref: str, expected_prefix: str) -> str:
    if not ref.startswith(expected_prefix):
        raise ValueError(f"Expected ref starting with {expected_prefix!r}; got {ref!r}")
    return ref.removeprefix(expected_prefix)


_STATUS_CODE_LENGTH = 3


def _is_2xx(status: str) -> bool:
    if status.upper() == "2XX":
        return True
    return len(status) == _STATUS_CODE_LENGTH and status[0] == "2" and status[1:].isdigit()
