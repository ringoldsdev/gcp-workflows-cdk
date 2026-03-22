"""Tests for the build() function.

build() accepts a dict of {filename: {name: Steps}} and writes YAML files.
Each workflow value must be a dict[str, Steps] with a required "main" key.
"""

import pytest
import yaml
from pathlib import Path

from cloud_workflows import (
    Steps,
    Assign,
    Call,
    Return,
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
        s = Steps()
        s.step("init", Assign(x=10, y=20))
        s.step("done", Return(expr("x + y")))

        written = build({"simple.yaml": {"main": s}}, output_dir=tmp_path)

        assert len(written) == 1
        assert written[0] == tmp_path / "simple.yaml"
        assert written[0].exists()

        expected = yaml.safe_load(load_fixture("cdk", "simple_assign.yaml"))
        actual = yaml.safe_load(written[0].read_text(encoding="utf-8"))
        assert actual == expected

    def test_multiple_workflows(self, tmp_path):
        main = Steps()
        main.step("call_helper", Call("helper", args={"input": "test"}, result="res"))
        main.step("done", Return(expr("res")))

        helper = Steps(params=["input"])
        helper.step("log", Call("sys.log", args={"text": expr("input")}))
        helper.step("done", Return("ok"))

        multi_dict = {"main": main, "helper": helper}

        second = Steps()
        second.step("done", Return("ok"))

        written = build(
            {"multi.yaml": multi_dict, "second.yaml": {"main": second}},
            output_dir=tmp_path,
        )

        assert len(written) == 2
        assert all(p.exists() for p in written)

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
        s = Steps()
        s.step("done", Return("ok"))

        written = build({"out.yaml": {"main": s}}, output_dir=tmp_path)

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

        s = Steps()
        s.step("done", Return("ok"))

        build({"out.yaml": {"main": s}}, output_dir=nested)

        assert nested.exists()
        assert (nested / "out.yaml").exists()

    def test_creates_subdirectory_in_filename(self, tmp_path):
        """Filenames with path separators create subdirectories."""
        s = Steps()
        s.step("done", Return("ok"))

        build({"sub/dir/out.yaml": {"main": s}}, output_dir=tmp_path)

        assert (tmp_path / "sub" / "dir" / "out.yaml").exists()

    def test_defaults_to_current_dir(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        s = Steps()
        s.step("done", Return("ok"))

        written = build({"default_dir.yaml": {"main": s}})

        assert (tmp_path / "default_dir.yaml").exists()
        assert written[0] == Path(".") / "default_dir.yaml"

    def test_accepts_string_output_dir(self, tmp_path):
        s = Steps()
        s.step("done", Return("ok"))

        build({"out.yaml": {"main": s}}, output_dir=str(tmp_path))

        assert (tmp_path / "out.yaml").exists()


# =============================================================================
# YAML content correctness
# =============================================================================


class TestBuildYamlContent:
    """build() produces correct YAML content."""

    def test_simple_workflow_yaml(self, tmp_path):
        s = Steps()
        s.step("init", Assign(x=10, y=20))
        s.step("done", Return(expr("x + y")))

        build({"flow.yaml": {"main": s}}, output_dir=tmp_path)

        content = (tmp_path / "flow.yaml").read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        assert parsed[0] == {"init": {"assign": [{"x": 10}, {"y": 20}]}}
        assert parsed[1] == {"done": {"return": "${x + y}"}}

    def test_subworkflows_yaml(self, tmp_path):
        main = Steps()
        main.step("done", Return("ok"))

        helper = Steps(params=["n"])
        helper.step("done", Return("also ok"))

        build(
            {"sub.yaml": {"main": main, "helper": helper}},
            output_dir=tmp_path,
        )

        content = (tmp_path / "sub.yaml").read_text(encoding="utf-8")
        parsed = yaml.safe_load(content)
        assert "main" in parsed
        assert "helper" in parsed
        assert parsed["helper"]["params"] == ["n"]

    def test_round_trip_through_build(self, tmp_path):
        """Build to file, read back, parse — should match original."""
        from cloud_workflows.models import parse_workflow

        s = Steps()
        s.step("init", Assign(x=42))
        s.step("done", Return(expr("x")))
        w1 = s._finalize()

        build({"rt.yaml": {"main": s}}, output_dir=tmp_path)

        w2 = parse_workflow((tmp_path / "rt.yaml").read_text(encoding="utf-8"))
        assert w1.to_dict() == w2.to_dict()


# =============================================================================
# Auto-finalization
# =============================================================================


class TestBuildAutoFinalize:
    """build() auto-finalizes dict-of-Steps."""

    def test_auto_finalize_simple(self, tmp_path):
        """Passing a dict with single 'main' Steps produces SimpleWorkflow."""
        s = Steps()
        s.step("init", Assign(x=1))
        s.step("done", Return(expr("x")))

        written = build({"auto.yaml": {"main": s}}, output_dir=tmp_path)

        content = yaml.safe_load(written[0].read_text(encoding="utf-8"))
        assert content[0] == {"init": {"assign": [{"x": 1}]}}
        assert content[1] == {"done": {"return": "${x}"}}

    def test_auto_finalize_multi(self, tmp_path):
        """Passing a dict of Steps for multi-workflow."""
        main = Steps()
        main.step("done", Return("ok"))

        helper = Steps(params=["n"])
        helper.step("done", Return(expr("n")))

        written = build(
            {"multi.yaml": {"main": main, "helper": helper}},
            output_dir=tmp_path,
        )

        content = yaml.safe_load(written[0].read_text(encoding="utf-8"))
        assert "main" in content
        assert "helper" in content


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
        s = Steps()
        s.step("done", Return("ok"))
        with pytest.raises(TypeError, match="filename must be a string"):
            build({123: {"main": s}}, output_dir=tmp_path)  # type: ignore[dict-item]

    def test_non_dict_value_raises(self, tmp_path):
        with pytest.raises(TypeError):
            build({"out.yaml": "not a workflow"}, output_dir=tmp_path)  # type: ignore[dict-item]

    def test_missing_main_key_raises(self, tmp_path):
        """Workflow dict must contain 'main' key."""
        s = Steps()
        s.step("done", Return("ok"))
        with pytest.raises(ValueError, match="'main' key"):
            build({"out.yaml": {"helper": s}}, output_dir=tmp_path)


# =============================================================================
# Composability
# =============================================================================


class TestBuildComposability:
    """build() works with composable step sequences."""

    def test_composable_steps(self, tmp_path):
        """Demonstrate composability via Steps merging."""

        def common_setup() -> Steps:
            s = Steps()
            s.step("setup", Assign(initialized=True))
            return s

        main = Steps()
        main.merge(common_setup())
        main.step("done", Return(expr("initialized")))

        written = build({"composed.yaml": {"main": main}}, output_dir=tmp_path)

        content = yaml.safe_load(written[0].read_text(encoding="utf-8"))
        assert content[0] == {"setup": {"assign": [{"initialized": True}]}}

    def test_factory_function_pattern(self, tmp_path):
        """A factory function can produce the full workflows dict."""

        def define_workflows():
            s = Steps()
            s.step("init", Assign(x=10))
            s.step("done", Return(expr("x")))
            return {"flow.yaml": {"main": s}}

        written = build(define_workflows(), output_dir=tmp_path)

        assert len(written) == 1
        assert written[0].exists()
        content = yaml.safe_load(written[0].read_text(encoding="utf-8"))
        assert content[0] == {"init": {"assign": [{"x": 10}]}}
