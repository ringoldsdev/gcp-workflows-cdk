"""Cloud Workflows YAML validator using Pydantic v2."""

from .models import (
    parse_workflow,
    to_yaml,
    expr,
    Workflow,
    SimpleWorkflow,
    SubworkflowsWorkflow,
    WorkflowDefinition,
    Step,
    AssignStep,
    CallStep,
    ReturnStep,
    RaiseStep,
    SwitchStep,
    SwitchCondition,
    ForStep,
    ForBody,
    ParallelStep,
    ParallelBody,
    Branch,
    TryStep,
    TryCallBody,
    TryStepsBody,
    ExceptBody,
    RetryConfig,
    BackoffConfig,
    NestedStepsStep,
)
from .builder import (
    WorkflowBuilder,
    StepBodyInput,
)
from .parser import (
    validate_yaml,
    validate_file,
    analyze_yaml,
    analyze_file,
    analyze_workflow,
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
    # Builder
    "WorkflowBuilder",
    "StepBodyInput",
    # Serialization
    "to_yaml",
    "expr",
    # Full analysis pipeline
    "analyze_yaml",
    "analyze_file",
    "analyze_workflow",
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
    # Model types (for programmatic construction)
    "WorkflowDefinition",
    "Step",
    "AssignStep",
    "CallStep",
    "ReturnStep",
    "RaiseStep",
    "SwitchStep",
    "SwitchCondition",
    "ForStep",
    "ForBody",
    "ParallelStep",
    "ParallelBody",
    "Branch",
    "TryStep",
    "TryCallBody",
    "TryStepsBody",
    "ExceptBody",
    "RetryConfig",
    "BackoffConfig",
    "NestedStepsStep",
]
