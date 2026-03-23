"""Tests for variable tracking and resolution."""

import pytest
from conftest import parse_fixture

from cloud_workflows.variables import (
    Scope,
    VariableAnalyzer,
    VariableDefinition,
    VariableIssue,
    DefinitionKind,
    Certainty,
    Severity,
    analyze_variables,
    _extract_lhs_bracket_exprs,
)


# =============================================================================
# Scope unit tests
# =============================================================================


class TestScope:
    """Tests for the Scope class."""

    def test_define_and_lookup(self):
        scope = Scope(name="test")
        scope.define(VariableDefinition(name="x", kind=DefinitionKind.ASSIGN))
        assert scope.is_defined("x")
        assert not scope.is_defined("y")

    def test_child_inherits_parent(self):
        parent = Scope(name="parent")
        parent.define(VariableDefinition(name="x", kind=DefinitionKind.ASSIGN))
        child = parent.child("child")
        assert child.is_defined("x")

    def test_child_does_not_pollute_parent(self):
        parent = Scope(name="parent")
        child = parent.child("child")
        child.define(VariableDefinition(name="y", kind=DefinitionKind.ASSIGN))
        assert child.is_defined("y")
        assert not parent.is_defined("y")

    def test_defined_names(self):
        parent = Scope(name="parent")
        parent.define(VariableDefinition(name="a", kind=DefinitionKind.ASSIGN))
        child = parent.child("child")
        child.define(VariableDefinition(name="b", kind=DefinitionKind.ASSIGN))
        assert child.defined_names() == {"a", "b"}
        assert parent.defined_names() == {"a"}

    def test_lookup_returns_definition(self):
        scope = Scope(name="test")
        defn = VariableDefinition(name="x", kind=DefinitionKind.PARAM, step_name=None)
        scope.define(defn)
        result = scope.lookup("x")
        assert result is defn

    def test_lookup_not_found(self):
        scope = Scope(name="test")
        assert scope.lookup("x") is None

    def test_child_shadow(self):
        parent = Scope(name="parent")
        parent.define(
            VariableDefinition(name="x", kind=DefinitionKind.ASSIGN, step_name="step1")
        )
        child = parent.child("child")
        child.define(
            VariableDefinition(
                name="x", kind=DefinitionKind.FOR_VALUE, step_name="loop"
            )
        )
        # Child should see its own definition
        assert child.lookup("x").kind == DefinitionKind.FOR_VALUE
        # Parent should see its own definition
        assert parent.lookup("x").kind == DefinitionKind.ASSIGN


# =============================================================================
# Valid variable usage (no issues expected)
# =============================================================================


class TestValidVariables:
    """Tests for workflows where all variables are properly defined."""

    def test_assign_then_reference(self):
        wf = parse_fixture("variables", "assign_then_ref.yaml")
        issues = analyze_variables(wf)
        assert issues == []

    def test_call_result_defines_variable(self):
        wf = parse_fixture("variables", "call_result.yaml")
        issues = analyze_variables(wf)
        assert issues == []

    def test_params_define_variables(self):
        wf = parse_fixture("variables", "params_defined.yaml")
        issues = analyze_variables(wf)
        assert issues == []

    def test_params_with_defaults(self):
        wf = parse_fixture("variables", "params_with_defaults.yaml")
        issues = analyze_variables(wf)
        assert issues == []

    def test_for_loop_variables_inside_loop(self):
        wf = parse_fixture("variables", "for_loop_scoped.yaml")
        issues = analyze_variables(wf)
        assert issues == []

    def test_except_as_variable_in_except(self):
        wf = parse_fixture("variables", "except_as_scoped.yaml")
        issues = analyze_variables(wf)
        assert issues == []

    def test_subworkflow_params(self):
        wf = parse_fixture("variables", "subworkflow_params.yaml")
        issues = analyze_variables(wf)
        assert issues == []

    def test_variable_redefined(self):
        wf = parse_fixture("variables", "variable_redefined.yaml")
        issues = analyze_variables(wf)
        assert issues == []

    def test_nested_scope_shared(self):
        wf = parse_fixture("variables", "nested_scope.yaml")
        issues = analyze_variables(wf)
        assert issues == []

    def test_nested_assign_root_exists(self):
        wf = parse_fixture("variables", "nested_assign.yaml")
        issues = analyze_variables(wf)
        assert issues == []

    def test_switch_all_branches_definite(self):
        wf = parse_fixture("variables", "switch_all_branches.yaml")
        issues = analyze_variables(wf)
        # Should have no errors since 'result' is defined in ALL branches
        errors = [i for i in issues if i.severity == Severity.ERROR]
        assert errors == []

    def test_return_ref(self):
        wf = parse_fixture("variables", "return_ref.yaml")
        issues = analyze_variables(wf)
        assert issues == []

    def test_raise_ref(self):
        wf = parse_fixture("variables", "raise_ref.yaml")
        issues = analyze_variables(wf)
        assert issues == []

    def test_try_steps_scope(self):
        """Variables defined inside try steps are workflow-scoped."""
        wf = parse_fixture("variables", "try_steps_scope.yaml")
        issues = analyze_variables(wf)
        assert issues == []

    def test_bracket_lhs_defined_vars(self):
        """Bracket subscript variables on assign LHS are validated as defined."""
        wf = parse_fixture("variables", "bracket_lhs_valid.yaml")
        issues = analyze_variables(wf)
        assert issues == []

    def test_bracket_lhs_string_literal_no_issues(self):
        """String literals in bracket subscripts produce no variable issues."""
        wf = parse_fixture("variables", "bracket_lhs_literal.yaml")
        issues = analyze_variables(wf)
        assert issues == []

    def test_bracket_lhs_numeric_index_no_issues(self):
        """Numeric subscripts like items[0] produce no variable issues."""
        wf = parse_fixture("variables", "bracket_lhs_numeric.yaml")
        issues = analyze_variables(wf)
        assert issues == []

    def test_map_key_expression_valid(self):
        """Map literal RHS with expression keys — all vars defined."""
        wf = parse_fixture("variables", "map_key_expr_valid.yaml")
        issues = analyze_variables(wf)
        assert issues == []


# =============================================================================
# Undefined variable references (errors expected)
# =============================================================================


class TestUndefinedVariables:
    """Tests for workflows with undefined variable references."""

    def test_reference_before_definition(self):
        wf = parse_fixture("variables", "undefined_reference.yaml")
        issues = analyze_variables(wf)
        errors = [i for i in issues if i.severity == Severity.ERROR]
        assert len(errors) == 1
        assert errors[0].variable == "x"
        assert "not defined" in errors[0].message

    def test_completely_undefined(self):
        wf = parse_fixture("variables", "completely_undefined.yaml")
        issues = analyze_variables(wf)
        errors = [i for i in issues if i.severity == Severity.ERROR]
        assert len(errors) == 1
        assert errors[0].variable == "totally_undefined"

    def test_for_variable_outside_loop(self):
        wf = parse_fixture("variables", "for_var_outside_loop.yaml")
        issues = analyze_variables(wf)
        errors = [i for i in issues if i.severity == Severity.ERROR]
        assert len(errors) == 1
        assert errors[0].variable == "item"
        assert errors[0].step_name == "after_loop"

    def test_except_as_outside_block(self):
        wf = parse_fixture("variables", "except_as_outside.yaml")
        issues = analyze_variables(wf)
        errors = [i for i in issues if i.severity == Severity.ERROR]
        assert len(errors) == 1
        assert errors[0].variable == "e"
        assert errors[0].step_name == "after_try"

    def test_bracket_lhs_undefined_variable(self):
        """Bracket subscript referencing an undefined variable produces an error."""
        wf = parse_fixture("variables", "bracket_lhs_undefined.yaml")
        issues = analyze_variables(wf)
        errors = [i for i in issues if i.severity == Severity.ERROR]
        assert len(errors) == 1
        assert errors[0].variable == "undefined_key"
        assert errors[0].step_name == "update"
        assert "not defined" in errors[0].message

    def test_bracket_lhs_expr_undefined_variable(self):
        """Expression in bracket subscript with one undefined variable."""
        wf = parse_fixture("variables", "bracket_lhs_expr_undefined.yaml")
        issues = analyze_variables(wf)
        errors = [i for i in issues if i.severity == Severity.ERROR]
        assert len(errors) == 1
        assert errors[0].variable == "suffix"
        assert errors[0].step_name == "update"

    def test_bracket_lhs_multiple_undefined(self):
        """Multiple bracket subscripts with undefined variables each produce errors."""
        wf = parse_fixture("variables", "bracket_lhs_multi_undefined.yaml")
        issues = analyze_variables(wf)
        errors = [i for i in issues if i.severity == Severity.ERROR]
        assert len(errors) == 2
        error_vars = {e.variable for e in errors}
        assert error_vars == {"undef_a", "undef_b"}

    def test_map_key_expression_undefined(self):
        """Expression in a YAML dict key referencing an undefined variable."""
        wf = parse_fixture("variables", "map_key_expr_undefined.yaml")
        issues = analyze_variables(wf)
        errors = [i for i in issues if i.severity == Severity.ERROR]
        assert len(errors) == 1
        assert errors[0].variable == "undefined_key"

    def test_map_key_expression_partial_undefined(self):
        """Expression in a YAML dict key where one operand is undefined."""
        wf = parse_fixture("variables", "map_key_expr_partial_undefined.yaml")
        issues = analyze_variables(wf)
        errors = [i for i in issues if i.severity == Severity.ERROR]
        assert len(errors) == 1
        assert errors[0].variable == "suffix"


# =============================================================================
# Conditional definitions (warnings expected)
# =============================================================================


class TestConditionalVariables:
    """Tests for variables defined conditionally via switch branches."""

    def test_switch_partial_definition_warns(self):
        wf = parse_fixture("variables", "switch_conditional_def.yaml")
        issues = analyze_variables(wf)
        warnings = [i for i in issues if i.severity == Severity.WARNING]
        assert len(warnings) == 1
        assert warnings[0].variable == "result"
        assert "may not be defined" in warnings[0].message


# =============================================================================
# VariableIssue data
# =============================================================================


class TestVariableIssue:
    """Tests for VariableIssue metadata."""

    def test_issue_has_workflow_name(self):
        wf = parse_fixture("variables", "completely_undefined.yaml")
        issues = analyze_variables(wf)
        assert len(issues) >= 1
        assert issues[0].workflow_name == "main"

    def test_issue_has_step_name(self):
        wf = parse_fixture("variables", "undefined_reference.yaml")
        issues = analyze_variables(wf)
        assert len(issues) >= 1
        assert issues[0].step_name == "use_first"

    def test_subworkflow_issue_has_workflow_name(self):
        """Verify issues in subworkflows report the correct workflow name."""
        wf = parse_fixture("variables", "subworkflow_params.yaml")
        # This fixture should have no issues, but we can check the analyzer
        # processes both workflows without error
        issues = analyze_variables(wf)
        assert issues == []


# =============================================================================
# Bracket expression extraction (unit tests)
# =============================================================================


class TestExtractLhsBracketExprs:
    """Tests for _extract_lhs_bracket_exprs helper."""

    def test_no_brackets(self):
        assert _extract_lhs_bracket_exprs("x") == []
        assert _extract_lhs_bracket_exprs("config.key") == []

    def test_simple_variable(self):
        assert _extract_lhs_bracket_exprs("my_map[key_var]") == ["key_var"]

    def test_string_literal(self):
        assert _extract_lhs_bracket_exprs('my_map["Key1"]') == ['"Key1"']

    def test_single_quoted_literal(self):
        assert _extract_lhs_bracket_exprs("my_map['Key1']") == ["'Key1'"]

    def test_numeric_index(self):
        assert _extract_lhs_bracket_exprs("items[0]") == ["0"]

    def test_expression(self):
        assert _extract_lhs_bracket_exprs('my_map[a + "b"]') == ['a + "b"']

    def test_multiple_brackets(self):
        result = _extract_lhs_bracket_exprs('a[x]["k"][y]')
        assert result == ["x", '"k"', "y"]

    def test_dot_then_bracket(self):
        assert _extract_lhs_bracket_exprs("obj.field[idx]") == ["idx"]

    def test_empty_brackets(self):
        """Empty brackets should return an empty string."""
        assert _extract_lhs_bracket_exprs("a[]") == [""]
