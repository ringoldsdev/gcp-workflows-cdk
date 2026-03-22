"""Tests for the cloud-workflows CLI.

Uses click.testing.CliRunner for isolated CLI invocation.
"""

import os
from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from cloud_workflows.cli import cli

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "cli"


@pytest.fixture
def runner():
    return CliRunner()


# =============================================================================
# generate command — stdout output
# =============================================================================


class TestGenerateStdout:
    """generate <file> prints YAML to stdout."""

    def test_prints_yaml(self, runner):
        result = runner.invoke(
            cli, ["generate", str(FIXTURES_DIR / "sample_workflow.py")]
        )
        assert result.exit_code == 0
        # Should contain valid YAML
        parsed = yaml.safe_load(result.output)
        assert isinstance(parsed, list)
        assert parsed[0]["init"]["assign"] == [{"x": 10}, {"y": 20}]

    def test_multi_workflow_prints_all(self, runner):
        result = runner.invoke(
            cli, ["generate", str(FIXTURES_DIR / "multi_workflow.py")]
        )
        assert result.exit_code == 0
        # Output should contain both workflows separated somehow
        assert "flow1.yaml" in result.output or "x: 1" in result.output
        assert "flow2.yaml" in result.output or "y: 2" in result.output


# =============================================================================
# generate command — dry-run (validate only)
# =============================================================================


class TestGenerateDryRun:
    """generate --dry-run validates but doesn't print YAML."""

    def test_valid_workflow(self, runner):
        result = runner.invoke(
            cli,
            ["generate", str(FIXTURES_DIR / "sample_workflow.py"), "--dry-run"],
        )
        assert result.exit_code == 0
        # Should indicate success
        assert "valid" in result.output.lower() or "ok" in result.output.lower()
        # Should NOT contain the YAML body
        assert "assign" not in result.output

    def test_invalid_workflow(self, runner):
        result = runner.invoke(
            cli,
            ["generate", str(FIXTURES_DIR / "invalid_workflow.py"), "--dry-run"],
        )
        # Should exit with non-zero code
        assert result.exit_code != 0
        # Should mention the issue
        assert "z" in result.output.lower() or "error" in result.output.lower()


# =============================================================================
# generate command — output-dir
# =============================================================================


class TestGenerateOutputDir:
    """generate --output-dir writes YAML files to disk."""

    def test_writes_file(self, runner, tmp_path):
        result = runner.invoke(
            cli,
            [
                "generate",
                str(FIXTURES_DIR / "sample_workflow.py"),
                "--output-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        output_file = tmp_path / "sample.yaml"
        assert output_file.exists()
        parsed = yaml.safe_load(output_file.read_text())
        assert isinstance(parsed, list)
        assert parsed[0]["init"]["assign"] == [{"x": 10}, {"y": 20}]

    def test_writes_multiple_files(self, runner, tmp_path):
        result = runner.invoke(
            cli,
            [
                "generate",
                str(FIXTURES_DIR / "multi_workflow.py"),
                "--output-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0
        assert (tmp_path / "flow1.yaml").exists()
        assert (tmp_path / "flow2.yaml").exists()

    def test_creates_output_dir(self, runner, tmp_path):
        output_dir = tmp_path / "new_dir"
        result = runner.invoke(
            cli,
            [
                "generate",
                str(FIXTURES_DIR / "sample_workflow.py"),
                "--output-dir",
                str(output_dir),
            ],
        )
        assert result.exit_code == 0
        assert (output_dir / "sample.yaml").exists()


# =============================================================================
# Error cases
# =============================================================================


class TestGenerateErrors:
    """CLI error handling."""

    def test_file_not_found(self, runner):
        result = runner.invoke(cli, ["generate", "nonexistent.py"])
        assert result.exit_code != 0

    def test_no_run_function(self, runner):
        result = runner.invoke(cli, ["generate", str(FIXTURES_DIR / "no_run.py")])
        assert result.exit_code != 0
        assert "run" in result.output.lower()

    def test_dry_run_and_output_dir_together(self, runner, tmp_path):
        """--dry-run and --output-dir are mutually exclusive."""
        result = runner.invoke(
            cli,
            [
                "generate",
                str(FIXTURES_DIR / "sample_workflow.py"),
                "--dry-run",
                "--output-dir",
                str(tmp_path),
            ],
        )
        assert result.exit_code != 0
