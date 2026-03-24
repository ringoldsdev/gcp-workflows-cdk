"""Shared test fixtures and helpers."""

import hashlib
import sys
import os
import textwrap
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
import yaml

from cloud_workflows.models import parse_workflow
from cloud_workflows.builder import _finalize, _to_yaml

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def parse(yaml_str: str):
    """Helper: dedent + parse a YAML string."""
    return parse_workflow(textwrap.dedent(yaml_str))


def load_fixture(*path_parts: str) -> str:
    """Load a YAML fixture file and return its contents as a string.

    Usage:
        load_fixture("assign", "basic.yaml")
        load_fixture("call", "http_get.yaml")
    """
    fixture_path = FIXTURES_DIR.joinpath(*path_parts)
    return fixture_path.read_text(encoding="utf-8")


def parse_fixture(*path_parts: str):
    """Load a YAML fixture file and parse it into a workflow.

    Usage:
        parse_fixture("assign", "basic.yaml")
    """
    return parse_workflow(load_fixture(*path_parts))


def _file_hash(path: Path) -> str:
    """Return the SHA-256 hex digest of a file's contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_steps_match_fixture(
    steps,
    *fixture_path_parts: str,
    tmp_path: Path,
) -> None:
    """Build a Steps container to a YAML file and compare against a fixture via file hash.

    This is the canonical "Python code in -> exact YAML out" test helper.

    1. Serializes ``steps.build()`` through ``yaml.dump()`` to produce YAML text.
    2. Writes the YAML text to a temp file.
    3. Computes the SHA-256 hash of that temp file.
    4. Computes the SHA-256 hash of the fixture file.
    5. Asserts the hashes match.

    On failure, prints both file paths and contents for easy debugging.

    Args:
        steps: A ``Steps`` instance to serialize.
        *fixture_path_parts: Path parts under ``tests/fixtures/`` (e.g. ``"cdk", "simple_assign.yaml"``).
        tmp_path: pytest ``tmp_path`` fixture for writing the output file.
    """
    # Serialize steps to YAML
    data = steps.build()
    yaml_str = yaml.dump(data, default_flow_style=False, sort_keys=False)

    # Write to temp file
    out_file = tmp_path / fixture_path_parts[-1]
    out_file.write_bytes(yaml_str.encode("utf-8"))

    # Compare hashes
    fixture_path = FIXTURES_DIR.joinpath(*fixture_path_parts)
    out_hash = _file_hash(out_file)
    fixture_hash = _file_hash(fixture_path)

    if out_hash != fixture_hash:
        actual_content = out_file.read_text(encoding="utf-8")
        expected_content = fixture_path.read_text(encoding="utf-8")
        pytest.fail(
            f"YAML output does not match fixture {'/'.join(fixture_path_parts)}\n"
            f"  output hash:  {out_hash}\n"
            f"  fixture hash: {fixture_hash}\n"
            f"--- expected (fixture) ---\n{expected_content}"
            f"--- actual (output) ---\n{actual_content}"
        )


def assert_workflow_match_fixture(
    workflow_dict,
    *fixture_path_parts: str,
    tmp_path: Path,
) -> None:
    """Finalize a workflow dict and compare the YAML output against a fixture via file hash.

    Like ``assert_steps_match_fixture`` but for full workflow dicts
    (``dict[str, Steps]``) that go through ``_finalize()`` + ``_to_yaml()``.

    Args:
        workflow_dict: A ``dict[str, Steps]`` with a required ``"main"`` key.
        *fixture_path_parts: Path parts under ``tests/fixtures/``.
        tmp_path: pytest ``tmp_path`` fixture for writing the output file.
    """
    data = _finalize(workflow_dict)
    yaml_str = _to_yaml(data)

    out_file = tmp_path / fixture_path_parts[-1]
    out_file.write_bytes(yaml_str.encode("utf-8"))

    fixture_path = FIXTURES_DIR.joinpath(*fixture_path_parts)
    out_hash = _file_hash(out_file)
    fixture_hash = _file_hash(fixture_path)

    if out_hash != fixture_hash:
        actual_content = out_file.read_text(encoding="utf-8")
        expected_content = fixture_path.read_text(encoding="utf-8")
        pytest.fail(
            f"YAML output does not match fixture {'/'.join(fixture_path_parts)}\n"
            f"  output hash:  {out_hash}\n"
            f"  fixture hash: {fixture_hash}\n"
            f"--- expected (fixture) ---\n{expected_content}"
            f"--- actual (output) ---\n{actual_content}"
        )


def assert_model_matches_fixture(
    workflow, *fixture_path_parts: str, tmp_path: Path
) -> None:
    """Assert that a Pydantic workflow model's YAML output matches a fixture via file hash.

    Args:
        workflow: A Pydantic workflow model (SimpleWorkflow or SubworkflowsWorkflow).
        *fixture_path_parts: Path parts under ``tests/fixtures/``.
        tmp_path: pytest ``tmp_path`` fixture for writing the output file.
    """
    yaml_str = workflow.to_yaml()

    out_file = tmp_path / fixture_path_parts[-1]
    out_file.write_bytes(yaml_str.encode("utf-8"))

    fixture_path = FIXTURES_DIR.joinpath(*fixture_path_parts)
    out_hash = _file_hash(out_file)
    fixture_hash = _file_hash(fixture_path)

    if out_hash != fixture_hash:
        actual_content = out_file.read_text(encoding="utf-8")
        expected_content = fixture_path.read_text(encoding="utf-8")
        pytest.fail(
            f"YAML output does not match fixture {'/'.join(fixture_path_parts)}\n"
            f"  output hash:  {out_hash}\n"
            f"  fixture hash: {fixture_hash}\n"
            f"--- expected (fixture) ---\n{expected_content}"
            f"--- actual (output) ---\n{actual_content}"
        )


def assert_passes_analysis(workflow) -> None:
    """Assert that analyze_workflow() and analyze_yaml() both pass validation.

    Args:
        workflow: A Pydantic workflow model (SimpleWorkflow or SubworkflowsWorkflow).
    """
    from cloud_workflows import analyze_workflow, analyze_yaml

    result = analyze_workflow(workflow)
    assert result.is_valid, f"analyze_workflow failed:\n  errors: {result.errors}"

    yaml_str = workflow.to_yaml()
    result2 = analyze_yaml(yaml_str)
    assert result2.is_valid, (
        f"analyze_yaml failed on serialized YAML:\n"
        f"  errors: {result2.errors}\n"
        f"  yaml:\n{yaml_str}"
    )
