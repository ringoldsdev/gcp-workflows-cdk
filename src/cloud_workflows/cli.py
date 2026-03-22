"""CLI for generating Cloud Workflows YAML from Python definition files.

Usage:
    cloud-workflows generate <file.py>                   # print YAML to stdout
    cloud-workflows generate <file.py> --dry-run         # validate only
    cloud-workflows generate <file.py> --output-dir dist # write files to dist/

Each Python file must define a run() function that returns:
    list[tuple[str, Workflow]]  — pairs of (filename, workflow)
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import click

from .models import SimpleWorkflow, SubworkflowsWorkflow
from .parser import analyze_workflow


@click.group()
def cli() -> None:
    """Cloud Workflows code generation tool."""


@cli.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, help="Validate only, don't output YAML.")
@click.option(
    "--output-dir",
    type=click.Path(),
    default=None,
    help="Write YAML files to this directory.",
)
def generate(file: str, dry_run: bool, output_dir: str | None) -> None:
    """Generate Cloud Workflows YAML from a Python definition file."""
    # --dry-run and --output-dir are mutually exclusive
    if dry_run and output_dir:
        raise click.UsageError("--dry-run and --output-dir are mutually exclusive.")

    # 1. Load the Python module
    module = _load_module(file)

    # 2. Call run()
    if not hasattr(module, "run") or not callable(module.run):
        raise click.ClickException(f"File '{file}' does not define a run() function.")

    workflows = module.run()
    if not isinstance(workflows, list):
        raise click.ClickException(
            f"run() must return a list[tuple[str, Workflow]], got {type(workflows).__name__}"
        )

    # 3. Process each (filename, workflow) pair
    has_errors = False
    for entry in workflows:
        if not isinstance(entry, tuple) or len(entry) != 2:
            raise click.ClickException(
                f"run() must return list of (filename, workflow) tuples, got {entry!r}"
            )
        filename, workflow = entry

        if not isinstance(workflow, (SimpleWorkflow, SubworkflowsWorkflow)):
            raise click.ClickException(
                f"Expected SimpleWorkflow or SubworkflowsWorkflow for '{filename}', "
                f"got {type(workflow).__name__}"
            )

        # Validate
        result = analyze_workflow(workflow)

        if not result.is_valid:
            has_errors = True
            click.echo(f"ERROR {filename}:", err=True)
            for error in result.errors:
                click.echo(f"  {error}", err=True)
            continue

        if dry_run:
            click.echo(f"OK {filename}: valid")
            continue

        yaml_str = workflow.to_yaml()

        if output_dir:
            out_path = Path(output_dir)
            out_path.mkdir(parents=True, exist_ok=True)
            out_file = out_path / filename
            out_file.write_text(yaml_str, encoding="utf-8")
            click.echo(f"Wrote {out_file}")
        else:
            # Print to stdout
            if len(workflows) > 1:
                click.echo(f"# --- {filename} ---")
            click.echo(yaml_str, nl=False)

    if has_errors:
        raise SystemExit(1)


def _load_module(file_path: str) -> Any:
    """Dynamically import a Python file as a module."""
    path = Path(file_path).resolve()
    module_name = path.stem

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise click.ClickException(f"Cannot load '{file_path}' as a Python module.")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise click.ClickException(f"Error loading '{file_path}': {e}")

    return module
