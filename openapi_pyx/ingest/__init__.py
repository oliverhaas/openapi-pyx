"""Ingest layer: load + validate an OpenAPI 3.1 spec."""

from openapi_pyx.ingest.loader import LoadError, load_spec

__all__ = ["LoadError", "load_spec"]
