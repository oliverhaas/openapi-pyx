"""Identifier sanitization for emitted code."""

import builtins
import keyword
import re

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_NON_IDENT = re.compile(r"[^A-Za-z0-9_]")
_MULTI_UNDERSCORE = re.compile(r"_+")
_PYTHON_RESERVED = set(keyword.kwlist) | set(dir(builtins))
_PYTHON_KEYWORDS = set(keyword.kwlist)


def snake_case(name: str) -> str:
    """Convert PascalCase/camelCase/kebab-case to snake_case, sanitizing non-identifier chars."""
    cleaned = _NON_IDENT.sub("_", name)
    cleaned = _CAMEL_BOUNDARY.sub("_", cleaned)
    cleaned = _MULTI_UNDERSCORE.sub("_", cleaned)
    if cleaned and cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return cleaned.lower()


def method_name(name: str) -> str:
    """Snake-cased method name with a trailing `_` if it would collide with a Python keyword or builtin."""
    snake = snake_case(name)
    return f"{snake}_" if snake in _PYTHON_RESERVED else snake


def model_name(name: str) -> str:
    """PascalCase model name with a trailing `_` if it would collide with a Python keyword or builtin."""
    parts = snake_case(name).split("_")
    pascal = "".join(p.capitalize() for p in parts if p)
    if not pascal or pascal[0].isdigit():
        pascal = f"_{pascal}"
    if pascal in _PYTHON_RESERVED or pascal.lower() in _PYTHON_RESERVED:
        return f"{pascal}_"
    return pascal


def field_name(name: str) -> str:
    """Snake-cased field name. Avoids Python keywords and Pydantic's leading-underscore restriction."""
    snake = snake_case(name)
    if snake in _PYTHON_KEYWORDS:
        return f"{snake}_"
    # Pydantic v2 rejects field names starting with `_` (reserved for private attrs).
    if snake.startswith("_"):
        return f"f{snake}"
    return snake


def module_name(name: str) -> str:
    """Snake-cased module name."""
    return snake_case(name)
