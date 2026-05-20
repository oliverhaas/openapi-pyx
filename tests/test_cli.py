from typer.testing import CliRunner

from openapi_pyx.cli import app

runner = CliRunner()


def test_cli_help_lists_generate_command():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "generate" in result.stdout


def test_generate_help():
    result = runner.invoke(app, ["generate", "--help"])
    assert result.exit_code == 0
    assert "spec" in result.stdout.lower()
    assert "out" in result.stdout.lower()
