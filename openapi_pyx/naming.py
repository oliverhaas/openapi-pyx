"""Identifier sanitization for emitted code."""

import builtins
import keyword
import re

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_PYTHON_RESERVED = set(keyword.kwlist) | set(dir(builtins))
_PYTHON_KEYWORDS = set(keyword.kwlist)


def snake_case(name: str) -> str:
    """Convert PascalCase/camelCase/kebab-case to snake_case."""
    cleaned = name.replace("-", "_").replace(" ", "_")
    cleaned = _CAMEL_BOUNDARY.sub("_", cleaned)
    return cleaned.lower()


def method_name(name: str) -> str:
    """Snake-cased method name with a trailing `_` if it would collide with a Python keyword or builtin."""
    snake = snake_case(name)
    return f"{snake}_" if snake in _PYTHON_RESERVED else snake


def model_name(name: str) -> str:
    """PascalCase model name with a trailing `_` if it would collide with a Python keyword or builtin."""
    parts = snake_case(name).split("_")
    pascal = "".join(p.capitalize() for p in parts if p)
    if pascal in _PYTHON_RESERVED or pascal.lower() in _PYTHON_RESERVED:
        return f"{pascal}_"
    return pascal


def field_name(name: str) -> str:
    """Snake-cased field name (class attribute). Only avoids Python keywords, not builtins."""
    snake = snake_case(name)
    return f"{snake}_" if snake in _PYTHON_KEYWORDS else snake


def module_name(name: str) -> str:
    """Snake-cased module name."""
    return snake_case(name)
