"""Cloud Workflows YAML validator using Pydantic v2."""

from .models import parse_workflow, Workflow, SimpleWorkflow, SubworkflowsWorkflow
from .parser import (
    validate_yaml,
    validate_file,
    analyze_yaml,
    analyze_file,
    AnalysisResult,
)
from .expressions import (
    validate_expression,
    validate_all_expressions,
    extract_expression_strings,
    extract_variable_references,
    ExpressionError,
)
from .variables import (
    analyze_variables,
    VariableIssue,
    Severity,
)

__all__ = [
    # Parsing
    "parse_workflow",
    "validate_yaml",
    "validate_file",
    "Workflow",
    "SimpleWorkflow",
    "SubworkflowsWorkflow",
    # Full analysis pipeline
    "analyze_yaml",
    "analyze_file",
    "AnalysisResult",
    # Expression validation
    "validate_expression",
    "validate_all_expressions",
    "extract_expression_strings",
    "extract_variable_references",
    "ExpressionError",
    # Variable analysis
    "analyze_variables",
    "VariableIssue",
    "Severity",
]
