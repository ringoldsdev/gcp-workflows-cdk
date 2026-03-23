"""Parser module: convenience functions for YAML validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Union

import yaml

from .expressions import ExpressionError, validate_all_expressions
from .models import (
    SimpleWorkflow,
    SubworkflowsWorkflow,
    Workflow,
    parse_workflow,
    validate_workflow,
)
from .variables import Severity, VariableIssue, analyze_variables


@dataclass
class AnalysisResult:
    """Full analysis result: parsed workflow + expression/variable issues."""

    workflow: Workflow
    expression_errors: List[ExpressionError] = field(default_factory=list)
    variable_issues: List[VariableIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True if no expression errors and no variable errors."""
        has_expr_errors = len(self.expression_errors) > 0
        has_var_errors = any(i.severity == Severity.ERROR for i in self.variable_issues)
        return not has_expr_errors and not has_var_errors

    @property
    def warnings(self) -> List[VariableIssue]:
        """Variable warnings (e.g., conditionally defined variables)."""
        return [i for i in self.variable_issues if i.severity == Severity.WARNING]

    @property
    def errors(self) -> List[Union[ExpressionError, VariableIssue]]:
        """All errors (expression + variable)."""
        result: List[Union[ExpressionError, VariableIssue]] = list(
            self.expression_errors
        )
        result.extend(i for i in self.variable_issues if i.severity == Severity.ERROR)
        return result


def analyze_yaml(yaml_str: str) -> AnalysisResult:
    """Parse, validate structure, validate expressions, and analyze variables.

    This is the full pipeline: structural validation (Pydantic), expression
    syntax validation, and variable reference checking.
    """
    # Step 1: Parse and validate structure
    workflow = parse_workflow(yaml_str)

    # Step 2: Validate expressions in raw YAML
    raw = yaml.safe_load(yaml_str)
    expr_errors = validate_all_expressions(raw)

    # Step 3: Analyze variable references
    var_issues = analyze_variables(workflow)

    return AnalysisResult(
        workflow=workflow,
        expression_errors=expr_errors,
        variable_issues=var_issues,
    )


def analyze_workflow(workflow: Any) -> AnalysisResult:
    """Full analysis pipeline for a workflow.

    Accepts either:
    - A Pydantic ``SimpleWorkflow`` or ``SubworkflowsWorkflow`` instance
    - Raw workflow data (list of step dicts or dict of workflow definitions)
      as produced by the builder layer's ``_finalize()``

    Raw data is validated through Pydantic first, then expressions and
    variable references are checked.
    """
    # If raw data, validate through Pydantic first
    if isinstance(workflow, (list, dict)) and not isinstance(
        workflow, (SimpleWorkflow, SubworkflowsWorkflow)
    ):
        workflow = validate_workflow(workflow)

    if not isinstance(workflow, (SimpleWorkflow, SubworkflowsWorkflow)):
        raise TypeError(
            f"Expected SimpleWorkflow, SubworkflowsWorkflow, list, or dict — "
            f"got {type(workflow).__name__}"
        )

    raw = workflow.to_dict()
    expr_errors = validate_all_expressions(raw)
    var_issues = analyze_variables(workflow)

    return AnalysisResult(
        workflow=workflow,
        expression_errors=expr_errors,
        variable_issues=var_issues,
    )
