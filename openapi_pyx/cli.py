"""Command-line interface for openapi-pyx."""

from __future__ import annotations

from pathlib import Path  # noqa: TC003

import typer

app = typer.Typer(help="OpenAPI 3.1 → Python client generator.")


@app.command()
def generate(
    spec: Path = typer.Argument(..., help="Path to an OpenAPI 3.1 spec (YAML or JSON)."),  # noqa: B008
    out: Path = typer.Option(..., "--out", "-o", help="Output directory for generated package."),  # noqa: B008
) -> None:
    """Generate a Python client from an OpenAPI 3.1 spec."""
    from openapi_pyx.generate import generate_client  # noqa: PLC0415

    generate_client(spec, out)
