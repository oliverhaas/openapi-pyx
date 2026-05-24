"""Typed IR for emitted Python source."""

from dataclasses import dataclass, field
from typing import Any, Literal

Variant = Literal["simple", "detailed"]


@dataclass(frozen=True, slots=True)
class TypeExpr:
    """A rendered Python type expression, e.g. `int | None` or `list[Pet]`."""

    rendered: str


@dataclass(frozen=True, slots=True)
class Import:
    """`import <name>` (optionally `as <alias>`)."""

    name: str
    alias: str | None = None


@dataclass(frozen=True, slots=True)
class ImportFrom:
    """`from <module> import <names>`."""

    module: str
    names: list[str]


@dataclass(frozen=True, slots=True)
class ModelField:
    name: str
    type_expr: TypeExpr
    required: bool
    default: str | None = None  # rendered as-is, e.g. "None" or '"open"'
    description: str | None = None
    examples: list[Any] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)  # Pydantic Field kwargs (ge, max_length, ...)
    serialization_alias: str | None = None  # set when name was sanitized away from original


@dataclass(frozen=True, slots=True)
class PydanticModel:
    name: str
    fields: list[ModelField]
    base: str = "BaseModel"
    docstring: str | None = None
    # `extra` config for `model_config`, e.g. "allow" / "forbid"
    extra: Literal["allow", "forbid", "ignore"] | None = None
    # When True, fields with aliases also accept the Python attribute name as input.
    populate_by_name: bool = False


@dataclass(frozen=True, slots=True)
class TypeAlias:
    """A top-level `Name: TypeAlias = expr` declaration."""

    name: str
    value: str


@dataclass(frozen=True, slots=True)
class Param:
    name: str
    type_expr: TypeExpr | None = None
    default: str | None = None
    keyword_only: bool = False


@dataclass(frozen=True, slots=True)
class ResponseBranch:
    """One status-code → schema branch for runtime dispatch in generated method bodies."""

    matcher: str  # Python expression over `resp.status_code`, e.g. `resp.status_code == 200`
    adapter: str | None  # `_Adapter_X` name, or None when the branch has no documented body
    type_expr: str | None  # rendered Python type for the parsed value, or None when no body
    is_default: bool = False  # True for the spec's `default` fallback (rendered as `else`)


@dataclass(frozen=True, slots=True)
class AsyncMethod:
    name: str
    params: list[Param]
    return_type: TypeExpr | None
    http_method: str  # lowercase: "get", "post", ...
    url_template: str  # may contain "{python_name}" segments
    query_params: list[tuple[str, str]]  # (over-the-wire name, python local name)
    path_params: list[tuple[str, str]]  # (template placeholder, python local name)
    header_params: list[tuple[str, str]]
    body_param: str | None  # python local name of the body parameter (or None)
    body_required: bool  # whether body is required (always True if body_param is None)
    body_type: TypeExpr | None  # type used to construct a `TypeAdapter` for serialization
    response_type: TypeExpr | None  # 2xx body type (for the simple variant's TypeAdapter + return)
    variant: Variant = "simple"
    branches: list[ResponseBranch] = field(default_factory=list)
    parsed_union_type: str | None = None  # union of all branch types | None, for the detailed variant
    docstring: str | None = None


@dataclass(frozen=True, slots=True)
class ClientClass:
    name: str
    methods: list[AsyncMethod]
    docstring: str | None = None


@dataclass(frozen=True, slots=True)
class SubClientAttr:
    """A `self.<attr> = <Cls>(...)` line in the top-level Client's `__init__`."""

    attr_name: str
    cls_name: str
    cls_module: str  # for the import


@dataclass(frozen=True, slots=True)
class RootClient:
    name: str
    sub_clients: list[SubClientAttr]
    docstring: str | None = None


@dataclass(frozen=True, slots=True)
class Assign:
    target: str
    value: str


Stmt = PydanticModel | TypeAlias | ClientClass | RootClient | Assign


@dataclass(frozen=True, slots=True)
class Module:
    docstring: str | None
    imports: list[Import | ImportFrom] = field(default_factory=list)
    body: list[Stmt] = field(default_factory=list)
