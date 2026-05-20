"""Render Code IR nodes to Python source strings."""

from __future__ import annotations

from openapi_pyx.codegen.nodes import (
    Assign,
    ClientClass,
    Import,
    ImportFrom,
    ModelField,
    Module,
    PydanticModel,
    RootClient,
    TypeAlias,
)

INDENT = "    "


def render_module(mod: Module) -> str:
    out: list[str] = []
    if mod.docstring is not None:
        out.append(f'"""{mod.docstring}"""')
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
        lines.append(f'{INDENT}"""{m.docstring}"""')
    if m.extra is not None:
        lines.append(f'{INDENT}model_config = {{"extra": "{m.extra}"}}')
    if not m.fields and not m.docstring and m.extra is None:
        lines.append(f"{INDENT}pass")
        return "\n".join(lines)
    lines.extend(f"{INDENT}{_render_model_field(f)}" for f in m.fields)
    return "\n".join(lines)


def _render_model_field(f: ModelField) -> str:
    base = f"{f.name}: {f.type_expr.rendered}"
    if f.serialization_alias is not None and f.default is not None:
        return f'{base} = Field({f.default}, alias="{f.serialization_alias}")'
    if f.serialization_alias is not None:
        return f'{base} = Field(alias="{f.serialization_alias}")'
    if f.default is not None:
        return f"{base} = {f.default}"
    return base


def _render_client_class(_c: ClientClass) -> str:
    # Filled out in Task 12.
    raise NotImplementedError


def _render_root_client(_c: RootClient) -> str:
    # Filled out in Task 13.
    raise NotImplementedError
