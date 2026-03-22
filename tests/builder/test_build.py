"""Tests for the build() function.

build() accepts a dict of {filename: workflow} and writes YAML files.
Workflow values can be finalized models or unfinalized Workflow builders
(auto-finalized by calling them).
"""

import pytest
import yaml
from pathlib import Path

from cloud_workflows import (
    StepBuilder,
    Workflow,
    Subworkflow,
    build,
    expr,
)
from cloud_workflows.models import SimpleWorkflow, SubworkflowsWorkflow
from conftest import load_fixture


# =============================================================================
# Basic file writing
# =============================================================================


class TestBuildWritesFiles:
    """build() writes YAML files to disk."""

    def test_single_workflow(self, tmp_path):
        w = Workflow().assign("init", x=10, y=20).returns("done", value=expr("x + y"))()

        written = build({"simple.yaml": w}, output_dir=tmp_path)

        assert len(written) == 1
        assert written[0] == tmp_path / "simple.yaml"
        assert written[0].exists()

        # Use cdk/ fixture (was build/simple.yaml, byte-identical)
        expected = yaml.safe_load(load_fixture("cdk", "simple_assign.yaml"))
        actual = yaml.safe_load(written[0].read_text(encoding="utf-8"))
        assert actual == expected

    def test_multiple_workflows(self, tmp_path):
        main = (
            Subworkflow()
            .call(
                "call_helper",
                func="helper",
                args={"input": "test"},
                result="res",
            )
            .returns("done", value=expr("res"))
        )
        helper = (
            Subworkflow(params=["input"])
            .call("log", func="sys.log", args={"text": expr("input")})
            .returns("done", value="ok")
        )
        multi = Workflow({"main": main, "helper": helper})()

        second = Workflow().returns("done", value="ok")()

        written = build(
            {"multi.yaml": multi, "second.yaml": second},
            output_dir=tmp_path,
        )

        assert len(written) == 2
        assert all(p.exists() for p in written)

        # Use cdk/ fixture (was build/multi.yaml, byte-identical)
        expected_multi = yaml.safe_load(load_fixture("cdk", "subworkflows.yaml"))
        actual_multi = yaml.safe_load(
            (tmp_path / "multi.yaml").read_text(encoding="utf-8")
        )
        assert actual_multi == expected_multi

        expected_second = yaml.safe_load(load_fixture("build", "second.yaml"))
        actual_second = yaml.safe_load(
            (tmp_path / "second.yaml").read_text(encoding="utf-8")
        )
        assert actual_second == expected_second

    def test_returns_path_objects(self, tmp_path):
        w = Workflow().returns("done", value="ok")()

        written = build({"out.yaml": w}, output_dir=tmp_path)

        assert isinstance(written, list)
        assert all(isinstance(p, Path) for p in written)


# =============================================================================
# Output directory handling
# =============================================================================


class TestBuildOutputDir:
    """build() handles output directory creation."""

    def test_creates_output_dir(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c"
        assert not nested.exists()

        w = Workflow().returns("done", value="ok")()

        build({"out.yaml": w}, output_dir=nested)

        assert nested.exists()
        assert (nested / "out.yaml").exists()

    def test_creates_subdirectory_in_filename(self, tmp_path):
        """Filenames with path separators create subdirectories."""
        w = Workflow().returns("done", value="ok")()

        build({"sub/dir/out.yaml": w}, output_dir=tmp_path)

        assert (tmp_path / "sub" / "dir" / "out.yaml").exists()

    def test_defaults_to_current_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        w = Workflow().returns("done", value="ok")()

        written = build({"default_dir.yaml": w})

        assert (tmp_path / "default_dir.yaml").exists()
        assert written[0] == Path(".") / "default_dir.yaml"

    def test_accepts_string_output_dir(self, tmp_path):
        w = Workflow().returns("done", value="ok")()

        build({"out.yaml": w}, output_dir=str(tmp_path))

        assert (tmp_path / "out.yaml").exists()


# =============================================================================
# YAML content correctness
# =============================================================================


class TestBuildYamlContent:
    """build() produces correct YAML content."""

    def test_simple_workflow_yaml(self, tmp_path):
        w = Workflow().assign("init", x=10, y=20).returns("done", value=expr("x + y"))()

        build({"flow.yaml": w}, output_dir=tmp_path)

        content = (tmp_path / "flow.yaml").read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        assert parsed[0] == {"init": {"assign": [{"x": 10}, {"y": 20}]}}
        assert parsed[1] == {"done": {"return": "${x + y}"}}

    def test_subworkflows_yaml(self, tmp_path):
        main = Subworkflow().returns("done", value="ok")
        helper = Subworkflow(params=["n"]).returns("done", value="also ok")
        w = Workflow({"main": main, "helper": helper})()

        build({"sub.yaml": w}, output_dir=tmp_path)

        content = (tmp_path / "sub.yaml").read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        assert "main" in parsed
        assert "helper" in parsed
        assert parsed["helper"]["params"] == ["n"]

    def test_round_trip_through_build(self, tmp_path):
        """Build to file, read back, parse -- should match original."""
        from cloud_workflows.models import parse_workflow

        w1 = Workflow().assign("init", x=42).returns("done", value=expr("x"))()

        build({"rt.yaml": w1}, output_dir=tmp_path)

        w2 = parse_workflow((tmp_path / "rt.yaml").read_text(encoding="utf-8"))
        assert w1.to_dict() == w2.to_dict()


# =============================================================================
# Auto-finalization
# =============================================================================


class TestBuildAutoFinalize:
    """build() auto-finalizes unfinalized Workflow builder instances."""

    def test_auto_finalize_simple(self, tmp_path):
        """Passing an unfinalized Workflow directly to build()."""
        written = build(
            {
                "auto.yaml": Workflow()
                .assign("init", x=1)
                .returns("done", value=expr("x"))
            },
            output_dir=tmp_path,
        )

        content = yaml.safe_load(written[0].read_text(encoding="utf-8"))
        assert content[0] == {"init": {"assign": [{"x": 1}]}}
        assert content[1] == {"done": {"return": "${x}"}}

    def test_auto_finalize_multi(self, tmp_path):
        """Passing an unfinalized multi-workflow Workflow."""
        main = Subworkflow().returns("done", value="ok")
        helper = Subworkflow(params=["n"]).returns("done", value=expr("n"))

        written = build(
            {"multi.yaml": Workflow({"main": main, "helper": helper})},
            output_dir=tmp_path,
        )

        content = yaml.safe_load(written[0].read_text(encoding="utf-8"))
        assert "main" in content
        assert "helper" in content

    def test_mix_finalized_and_unfinalized(self, tmp_path):
        """Dict can contain both finalized models and unfinalized builders."""
        finalized = Workflow().returns("done", value="ok")()
        unfinalized = Workflow().assign("init", x=1).returns("done", value=expr("x"))

        written = build(
            {"a.yaml": finalized, "b.yaml": unfinalized},
            output_dir=tmp_path,
        )

        assert len(written) == 2
        assert all(p.exists() for p in written)


# =============================================================================
# Workflow callable
# =============================================================================


class TestWorkflowCallable:
    """Workflow instances can be called to finalize."""

    def test_call_returns_simple_workflow(self):
        w = Workflow().assign("init", x=10).returns("done", value=expr("x"))()
        assert isinstance(w, SimpleWorkflow)

    def test_call_returns_subworkflows_workflow(self):
        main = Subworkflow().returns("done", value="ok")
        helper = Subworkflow(params=["n"]).returns("done", value=expr("n"))
        w = Workflow({"main": main, "helper": helper})()
        assert isinstance(w, SubworkflowsWorkflow)

    def test_call_same_as_build(self):
        """() and .build() produce identical results."""
        w1 = Workflow().assign("init", x=10).returns("done", value=expr("x"))
        w2 = Workflow().assign("init", x=10).returns("done", value=expr("x"))

        assert w1().to_dict() == w2.build().to_dict()


# =============================================================================
# Error handling
# =============================================================================


class TestBuildErrors:
    """build() validates its inputs."""

    def test_empty_dict_raises(self, tmp_path):
        with pytest.raises(ValueError, match="must not be empty"):
            build({}, output_dir=tmp_path)

    def test_non_dict_raises(self, tmp_path):
        with pytest.raises(TypeError, match="must be a dict"):
            build([("a.yaml", "b")], output_dir=tmp_path)  # type: ignore[arg-type]

    def test_non_string_key_raises(self, tmp_path):
        w = Workflow().returns("done", value="ok")()
        with pytest.raises(TypeError, match="filename must be a string"):
            build({123: w}, output_dir=tmp_path)  # type: ignore[dict-item]

    def test_non_workflow_value_raises(self, tmp_path):
        with pytest.raises(TypeError, match="Workflow"):
            build({"out.yaml": {"not": "a workflow"}}, output_dir=tmp_path)  # type: ignore[dict-item]


# =============================================================================
# Composability (replaces old TestRunConvention)
# =============================================================================


class TestBuildComposability:
    """build() works with composable step builders and helper functions."""

    def test_composable_steps(self, tmp_path):
        """Demonstrate composability via StepBuilder.apply()."""

        def common_setup() -> StepBuilder:
            return StepBuilder().assign("setup", initialized=True)

        w = (
            Workflow().apply(common_setup()).returns("done", value=expr("initialized"))
        )()

        written = build({"composed.yaml": w}, output_dir=tmp_path)

        content = yaml.safe_load(written[0].read_text(encoding="utf-8"))
        assert content[0] == {"setup": {"assign": [{"initialized": True}]}}

    def test_factory_function_pattern(self, tmp_path):
        """A factory function can produce the full workflows dict."""

        def define_workflows():
            w = Workflow().assign("init", x=10).returns("done", value=expr("x"))()
            return {"flow.yaml": w}

        written = build(define_workflows(), output_dir=tmp_path)

        assert len(written) == 1
        assert written[0].exists()
        content = yaml.safe_load(written[0].read_text(encoding="utf-8"))
        assert content[0] == {"init": {"assign": [{"x": 10}]}}
