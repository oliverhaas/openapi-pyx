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


def render_module(mod: Module, *, sync: bool = False) -> str:
    out: list[str] = []
    if mod.docstring is not None:
        out.append(_docstring(mod.docstring))
        out.append("")
    out.extend(_render_import(imp, sync=sync) for imp in mod.imports)
    if mod.imports:
        out.append("")
    for i, stmt in enumerate(mod.body):
        out.append(_render_stmt(stmt, sync=sync))
        if i != len(mod.body) - 1:
            out.append("")
            out.append("")
    return "\n".join(out) + ("\n" if out else "")


def _render_import(imp: Import | ImportFrom, *, sync: bool = False) -> str:  # noqa: ARG001
    if isinstance(imp, Import):
        return f"import {imp.name}" + (f" as {imp.alias}" if imp.alias else "")
    return f"from {imp.module} import {', '.join(imp.names)}"


def _render_stmt(stmt: object, *, sync: bool = False) -> str:
    if isinstance(stmt, PydanticModel):
        return _render_pydantic_model(stmt)
    if isinstance(stmt, ClientClass):
        return _render_client_class(stmt, sync=sync)
    if isinstance(stmt, RootClient):
        return _render_root_client(stmt, sync=sync)
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


def _render_client_class(c: ClientClass, *, sync: bool = False) -> str:
    httpx_client = "httpx.Client" if sync else "httpx.AsyncClient"
    lines = [f"class {c.name}:"]
    if c.docstring:
        lines.append(_docstring(c.docstring, INDENT))
    lines.append(f"{INDENT}def __init__(self, http: {httpx_client}) -> None:")
    lines.append(f"{INDENT * 2}self._http = http")
    for method in c.methods:
        lines.append("")
        lines.append(_render_method(method, sync=sync))
    return "\n".join(lines)


def _render_method(m: AsyncMethod, *, sync: bool = False) -> str:
    sig_params = _render_params(m.params)
    return_anno = f" -> {m.return_type.rendered}" if m.return_type else " -> None"
    keyword = "def " if sync else "async def "
    head = f"{INDENT}{keyword}{m.name}({sig_params}){return_anno}:"
    body = _render_method_body(m, sync=sync)
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


def _render_method_body(m: AsyncMethod, *, sync: bool = False) -> str:  # noqa: C901, PLR0912
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

    base_args = [url_expr]
    if m.query_params:
        base_args.append("params=params")
    if have_headers:
        base_args.append("headers=headers")

    awaited = "" if sync else "await "
    if m.body_param and m.body_type is not None:
        body_dump = f"{_adapter_name(m.body_type)}.dump_json({m.body_param}, by_alias=True, exclude_none=True)"
        if not m.body_required:
            lines.append(f"{indent}if {m.body_param} is not None:")
            with_body = [*base_args, f"content={body_dump}"]
            lines.append(f"{indent}{INDENT}resp = {awaited}self._http.{m.http_method}({', '.join(with_body)})")
            lines.append(f"{indent}else:")
            lines.append(f"{indent}{INDENT}resp = {awaited}self._http.{m.http_method}({', '.join(base_args)})")
        else:
            full_args = [*base_args, f"content={body_dump}"]
            lines.append(f"{indent}resp = {awaited}self._http.{m.http_method}({', '.join(full_args)})")
    else:
        lines.append(f"{indent}resp = {awaited}self._http.{m.http_method}({', '.join(base_args)})")

    if m.variant == "detailed":
        lines.extend(_render_detailed_response(m, indent))
    else:
        lines.extend(_render_simple_response(m, indent))

    return "\n".join(lines)


def _render_simple_response(m: AsyncMethod, indent: str) -> list[str]:
    """Emit the 2xx-or-raise dispatch for the simple variant."""
    lines: list[str] = []
    success_branches = [b for b in m.branches if not b.is_default and _is_2xx_matcher(b.matcher)]
    error_branches = [b for b in m.branches if b not in success_branches]

    for b in success_branches:
        lines.append(f"{indent}if {b.matcher}:")
        if b.adapter and m.response_type is not None:
            lines.append(f"{indent}{INDENT}return {b.adapter}.validate_json(resp.content)")
        else:
            lines.append(f"{indent}{INDENT}return None")

    if not success_branches and m.response_type is None:
        # No documented 2xx at all; raise on anything non-2xx.
        lines.append(f"{indent}if 200 <= resp.status_code < 300:")
        lines.append(f"{indent}{INDENT}return None")

    # Error dispatch: try to parse documented error bodies, then raise.
    lines.append(f"{indent}parsed: object | None = None")
    for b in error_branches:
        if b.is_default:
            if b.adapter:
                lines.append(f"{indent}if True:  # default")
                lines.append(f"{indent}{INDENT}parsed = {b.adapter}.validate_json(resp.content)")
            continue
        if b.adapter is None:
            continue
        lines.append(f"{indent}if {b.matcher}:")
        lines.append(f"{indent}{INDENT}parsed = {b.adapter}.validate_json(resp.content)")
    lines.append(f"{indent}raise ApiError(resp.status_code, resp.content, dict(resp.headers), parsed)")
    return lines


def _render_detailed_response(m: AsyncMethod, indent: str) -> list[str]:
    """Emit the never-raise dispatch for the detailed variant, returning Response[T]."""
    lines: list[str] = []
    parsed_type = m.parsed_union_type or "None"
    lines.append(f"{indent}parsed: {parsed_type} = None")
    bodied = [b for b in m.branches if b.adapter is not None]
    for i, b in enumerate(bodied):
        prefix = "if" if i == 0 else "elif"
        if b.is_default:
            kw = "else" if i > 0 else "if True"
            lines.append(f"{indent}{kw}:")
        else:
            lines.append(f"{indent}{prefix} {b.matcher}:")
        lines.append(f"{indent}{INDENT}parsed = {b.adapter}.validate_json(resp.content)")
    lines.append(
        f"{indent}return Response(status_code=resp.status_code, "
        f"headers=dict(resp.headers), content=resp.content, parsed=parsed)",
    )
    return lines


def _is_2xx_matcher(matcher: str) -> bool:
    """Heuristic: does this matcher expression target a 2xx status?"""
    if "200 <= resp.status_code < 300" in matcher:
        return True
    if "resp.status_code == " in matcher:
        code = int(matcher.rsplit(" ", 1)[-1])
        return 200 <= code < 300  # noqa: PLR2004
    return False


def _render_url_expr(template: str, path_params: list[tuple[str, str]]) -> str:
    if not path_params:
        return f'"{template}"'
    out = template
    for placeholder, local in path_params:
        # Percent-encode each segment so spaces, slashes, and other reserved chars don't break the URL.
        out = out.replace("{" + placeholder + "}", "{quote(str(" + local + '), safe="")}')
    return f'f"{out}"'


def _adapter_name(t: TypeExpr) -> str:
    safe = "".join(c if c.isalnum() else "_" for c in t.rendered)
    return f"_Adapter_{safe}"


def _render_root_client(c: RootClient, *, sync: bool = False) -> str:
    httpx_client = "httpx.Client" if sync else "httpx.AsyncClient"
    enter, exit_ = ("__enter__", "__exit__") if sync else ("__aenter__", "__aexit__")
    aclose = "close" if sync else "aclose"
    async_kw = "" if sync else "async "
    await_kw = "" if sync else "await "

    lines = [f"class {c.name}:"]
    if c.docstring:
        lines.append(_docstring(c.docstring, INDENT))
    init_sig = (
        f"{INDENT}def __init__("
        "self, base_url: str, *, "
        f"http: {httpx_client} | None = None, "
        "timeout: httpx.Timeout | float | None = None, "
        "headers: dict[str, str] | None = None, "
        "cookies: dict[str, str] | None = None, "
        "verify: bool | str | ssl.SSLContext = True, "
        "follow_redirects: bool = False, "
        "httpx_args: dict[str, object] | None = None,"
        ") -> None:"
    )
    construct_http = (
        f"{INDENT * 2}self._http = http or {httpx_client}(\n"
        f"{INDENT * 3}base_url=base_url,\n"
        f"{INDENT * 3}timeout=timeout if timeout is not None else httpx.Timeout(5.0),\n"
        f"{INDENT * 3}headers=headers or {{}},\n"
        f"{INDENT * 3}cookies=cookies or {{}},\n"
        f"{INDENT * 3}verify=verify,\n"
        f"{INDENT * 3}follow_redirects=follow_redirects,\n"
        f"{INDENT * 3}**(httpx_args or {{}}),\n"
        f"{INDENT * 2})"
    )
    lines.extend(
        [
            init_sig,
            construct_http,
            *[f"{INDENT * 2}self.{sc.attr_name} = {sc.cls_name}(self._http)" for sc in c.sub_clients],
            "",
            f'{INDENT}{async_kw}def {enter}(self) -> "{c.name}":',
            f"{INDENT * 2}return self",
            "",
            f"{INDENT}{async_kw}def {exit_}(self, *_exc: object) -> None:",
            f"{INDENT * 2}{await_kw}self._http.{aclose}()",
        ],
    )
    return "\n".join(lines)
