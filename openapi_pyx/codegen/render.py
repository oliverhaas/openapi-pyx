"""Render Code IR nodes to Python source strings."""

from __future__ import annotations

from openapi_pyx.codegen.nodes import (
    Assign,
    AsyncMethod,
    ClientClass,
    Import,
    ImportFrom,
    ModelField,
    Module,
    Param,
    PydanticModel,
    RootClient,
    TypeAlias,
    TypeExpr,
)

INDENT = "    "


def _docstring(text: str, indent: str = "") -> str:
    """Wrap `text` as a `\"\"\"...\"\"\"` docstring at `indent` level, multi-line aware."""
    escaped = text.replace('"""', '\\"\\"\\"')
    if escaped.endswith('"'):
        escaped += " "
    if "\n" not in escaped:
        return f'{indent}"""{escaped}"""'
    lines = escaped.split("\n")
    rendered = [f'{indent}"""{lines[0]}']
    rendered.extend(f"{indent}{line}" if line else "" for line in lines[1:])
    rendered.append(f'{indent}"""')
    return "\n".join(rendered)


def render_module(mod: Module) -> str:
    out: list[str] = []
    if mod.docstring is not None:
        out.append(_docstring(mod.docstring))
        out.append("")
    out.extend(_render_import(imp) for imp in mod.imports)
    if mod.imports:
        out.append("")
    for i, stmt in enumerate(mod.body):
        out.append(_render_stmt(stmt))
        if i != len(mod.body) - 1:
            out.append("")
            out.append("")
    return "\n".join(out) + ("\n" if out else "")


def _render_import(imp: Import | ImportFrom) -> str:
    if isinstance(imp, Import):
        return f"import {imp.name}" + (f" as {imp.alias}" if imp.alias else "")
    return f"from {imp.module} import {', '.join(imp.names)}"


def _render_stmt(stmt: object) -> str:
    if isinstance(stmt, PydanticModel):
        return _render_pydantic_model(stmt)
    if isinstance(stmt, ClientClass):
        return _render_client_class(stmt)
    if isinstance(stmt, RootClient):
        return _render_root_client(stmt)
    if isinstance(stmt, TypeAlias):
        return f"{stmt.name} = {stmt.value}"
    if isinstance(stmt, Assign):
        return f"{stmt.target} = {stmt.value}"
    raise TypeError(f"Unknown stmt: {type(stmt).__name__}")


def _render_pydantic_model(m: PydanticModel) -> str:
    lines = [f"class {m.name}({m.base}):"]
    if m.docstring:
        lines.append(_docstring(m.docstring, INDENT))
    config_args: list[str] = []
    if m.extra is not None:
        config_args.append(f'extra="{m.extra}"')
    if m.populate_by_name:
        config_args.append("populate_by_name=True")
    if config_args:
        lines.append(f"{INDENT}model_config = ConfigDict({', '.join(config_args)})")
    if not m.fields and not m.docstring and not config_args:
        lines.append(f"{INDENT}pass")
        return "\n".join(lines)
    lines.extend(f"{INDENT}{_render_model_field(f)}" for f in m.fields)
    return "\n".join(lines)


def _render_model_field(f: ModelField) -> str:
    base = f"{f.name}: {f.type_expr.rendered}"
    if f.serialization_alias is None and not f.description and not f.examples and not f.constraints:
        if f.default is not None:
            return f"{base} = {f.default}"
        return base
    args: list[str] = []
    if f.default is not None:
        args.append(f.default)
    if f.serialization_alias is not None:
        args.append(f'alias="{f.serialization_alias}"')
    if f.description:
        args.append(f"description={_string_literal(f.description)}")
    if f.examples:
        args.append(f"examples={f.examples!r}")
    for k, v in f.constraints.items():
        args.append(f"{k}={v!r}")
    return f"{base} = Field({', '.join(args)})"


def _string_literal(text: str) -> str:
    """Render `text` as a Python string literal that round-trips through ruff format."""
    return repr(text)


def _render_client_class(c: ClientClass) -> str:
    lines = [f"class {c.name}:"]
    if c.docstring:
        lines.append(_docstring(c.docstring, INDENT))
    lines.append(f"{INDENT}def __init__(self, http: httpx.AsyncClient) -> None:")
    lines.append(f"{INDENT * 2}self._http = http")
    for method in c.methods:
        lines.append("")
        lines.append(_render_async_method(method))
    return "\n".join(lines)


def _render_async_method(m: AsyncMethod) -> str:
    sig_params = _render_params(m.params)
    return_anno = f" -> {m.return_type.rendered}" if m.return_type else " -> None"
    head = f"{INDENT}async def {m.name}({sig_params}){return_anno}:"
    body = _render_method_body(m)
    return head + "\n" + body


def _render_params(params: list[Param]) -> str:
    rendered: list[str] = []
    have_kw_marker = False
    for p in params:
        if p.keyword_only and not have_kw_marker:
            rendered.append("*")
            have_kw_marker = True
        rendered.append(_render_param(p))
    return ", ".join(rendered)


def _render_param(p: Param) -> str:
    if p.type_expr is None:
        return p.name
    out = f"{p.name}: {p.type_expr.rendered}"
    if p.default is not None:
        out += f" = {p.default}"
    return out


def _render_method_body(m: AsyncMethod) -> str:  # noqa: C901, PLR0912
    indent = INDENT * 2
    lines: list[str] = []
    if m.docstring:
        lines.append(_docstring(m.docstring, indent))

    url_expr = _render_url_expr(m.url_template, m.path_params)

    if m.query_params:
        lines.append(f"{indent}params: dict[str, object] = {{}}")
        for wire, local in m.query_params:
            lines.append(f"{indent}if {local} is not None:")
            lines.append(f'{indent}{INDENT}params["{wire}"] = {local}')

    have_headers = bool(m.header_params)
    if m.header_params:
        lines.append(f"{indent}headers: dict[str, str] = {{}}")
        for wire, local in m.header_params:
            lines.append(f"{indent}if {local} is not None:")
            lines.append(f'{indent}{INDENT}headers["{wire}"] = {local}')

    if m.body_param:
        if have_headers:
            lines.append(f'{indent}headers["Content-Type"] = "application/json"')
        else:
            lines.append(f'{indent}headers = {{"Content-Type": "application/json"}}')
            have_headers = True

    # Build the call. If body is optional, the content= arg is conditional.
    base_args = [url_expr]
    if m.query_params:
        base_args.append("params=params")
    if have_headers:
        base_args.append("headers=headers")

    if m.body_param and not m.body_required:
        # Emit a conditional based on whether body was provided.
        lines.append(f"{indent}if {m.body_param} is not None:")
        with_body = [*base_args, f"content={m.body_param}.model_dump_json(by_alias=True, exclude_none=True)"]
        lines.append(f"{indent}{INDENT}resp = await self._http.{m.http_method}({', '.join(with_body)})")
        lines.append(f"{indent}else:")
        lines.append(f"{indent}{INDENT}resp = await self._http.{m.http_method}({', '.join(base_args)})")
    elif m.body_param:
        full_args = [*base_args, f"content={m.body_param}.model_dump_json(by_alias=True, exclude_none=True)"]
        lines.append(f"{indent}resp = await self._http.{m.http_method}({', '.join(full_args)})")
    else:
        lines.append(f"{indent}resp = await self._http.{m.http_method}({', '.join(base_args)})")

    lines.append(f"{indent}resp.raise_for_status()")

    if m.response_type is not None:
        lines.append(f"{indent}return {_adapter_name(m.response_type)}.validate_json(resp.content)")

    return "\n".join(lines)


def _render_url_expr(template: str, path_params: list[tuple[str, str]]) -> str:
    if not path_params:
        return f'"{template}"'
    out = template
    for placeholder, local in path_params:
        out = out.replace("{" + placeholder + "}", "{" + local + "}")
    return f'f"{out}"'


def _adapter_name(t: TypeExpr) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in t.rendered)
    return f"_Adapter_{safe}"


def _render_root_client(c: RootClient) -> str:
    lines = [
        f"class {c.name}:",
    ]
    if c.docstring:
        lines.append(_docstring(c.docstring, INDENT))
    lines.extend(
        [
            f"{INDENT}def __init__(self, base_url: str, *, http: httpx.AsyncClient | None = None) -> None:",
            f"{INDENT * 2}self._http = http or httpx.AsyncClient(base_url=base_url)",
            *[f"{INDENT * 2}self.{sc.attr_name} = {sc.cls_name}(self._http)" for sc in c.sub_clients],
            "",
            f'{INDENT}async def __aenter__(self) -> "{c.name}":',
            f"{INDENT * 2}return self",
            "",
            f"{INDENT}async def __aexit__(self, *_exc: object) -> None:",
            f"{INDENT * 2}await self._http.aclose()",
        ],
    )
    return "\n".join(lines)
