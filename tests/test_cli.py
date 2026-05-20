from pathlib import Path

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


def test_generate_command_writes_files(tmp_path: Path):
    fixtures = Path(__file__).parent / "fixtures"
    out = tmp_path / "out"
    result = runner.invoke(app, [str(fixtures / "petstore.yaml"), "--out", str(out)])
    assert result.exit_code == 0, result.stdout + result.stderr
    assert (out / "client.py").exists()
    assert (out / "models.py").exists()
