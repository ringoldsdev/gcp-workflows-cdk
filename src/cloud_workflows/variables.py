"""Variable tracking and resolution for GCP Cloud Workflows.

Walks a parsed workflow model, builds a scope/symbol table, and checks that
all variable references in expressions resolve to defined variables.

Scoping rules:
- Variables have workflow-level scope within a subworkflow (or main).
- `assign` steps define variables visible to all subsequent steps.
- `result` fields on `call`/`try` steps define variables.
- `params` on workflow definitions define variables at workflow start.
- `for` loop variables (value, index) are loop-scoped (not visible outside).
- `except as` variables are scoped to the except block.
- Parallel branch variables are branch-local. Only `shared` variables are
  written to from branches.
- Variables defined conditionally (inside only some switch branches) are
  tracked as "maybe defined" -- references to them produce warnings, not errors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Union

from .expressions import extract_expression_strings, extract_variable_references
from .models import (
    AssignStep,
    Branch,
    CallStep,
    ExceptBody,
    ForBody,
    ForStep,
    NestedStepsStep,
    ParallelBody,
    ParallelStep,
    RaiseStep,
    ReturnStep,
    SimpleWorkflow,
    Step,
    SubworkflowsWorkflow,
    SwitchCondition,
    SwitchStep,
    TryCallBody,
    TryStep,
    TryStepsBody,
    Workflow,
    WorkflowDefinition,
)


# =============================================================================
# Data types
# =============================================================================


class DefinitionKind(Enum):
    """How a variable was defined."""

    PARAM = auto()
    ASSIGN = auto()
    RESULT = auto()
    FOR_VALUE = auto()
    FOR_INDEX = auto()
    EXCEPT_AS = auto()


class Certainty(Enum):
    """Whether a variable is definitely or maybe defined at a given point."""

    DEFINITE = auto()
    MAYBE = auto()  # e.g., defined in only some switch branches


@dataclass
class VariableDefinition:
    """Record of where and how a variable was defined."""

    name: str
    kind: DefinitionKind
    certainty: Certainty = Certainty.DEFINITE
    step_name: Optional[str] = None  # the step that defined it


class Severity(Enum):
    ERROR = auto()
    WARNING = auto()


@dataclass
class VariableIssue:
    """A variable-related issue found during analysis."""

    severity: Severity
    message: str
    variable: str
    step_name: Optional[str] = None
    workflow_name: Optional[str] = None


# =============================================================================
# Scope
# =============================================================================


class Scope:
    """A scope for variable definitions.

    Supports nested scopes (for loops, except blocks, parallel branches).
    Looking up a variable checks the current scope and all parent scopes.
    """

    def __init__(self, parent: Optional[Scope] = None, name: str = ""):
        self.parent = parent
        self.name = name
        self._vars: Dict[str, VariableDefinition] = {}

    def define(self, var: VariableDefinition) -> None:
        self._vars[var.name] = var

    def lookup(self, name: str) -> Optional[VariableDefinition]:
        if name in self._vars:
            return self._vars[name]
        if self.parent is not None:
            return self.parent.lookup(name)
        return None

    def is_defined(self, name: str) -> bool:
        return self.lookup(name) is not None

    def defined_names(self) -> Set[str]:
        names = set(self._vars.keys())
        if self.parent is not None:
            names |= self.parent.defined_names()
        return names

    def child(self, name: str = "") -> Scope:
        return Scope(parent=self, name=name)


# =============================================================================
# Analyzer
# =============================================================================


class VariableAnalyzer:
    """Walks a parsed workflow and checks variable references."""

    def __init__(self):
        self.issues: List[VariableIssue] = []
        self._subworkflow_names: Set[str] = set()

    def analyze(self, workflow: Workflow) -> List[VariableIssue]:
        """Analyze a workflow for variable issues. Returns list of issues."""
        self.issues = []

        if isinstance(workflow, SimpleWorkflow):
            scope = Scope(name="main")
            self._analyze_steps(workflow.steps, scope, workflow_name="main")
        elif isinstance(workflow, SubworkflowsWorkflow):
            # Collect subworkflow names first (they can be called from each other)
            self._subworkflow_names = set(workflow.workflows.keys())
            for wf_name, wf_def in workflow.workflows.items():
                scope = Scope(name=wf_name)
                # Define params as variables
                if wf_def.params:
                    for param in wf_def.params:
                        if isinstance(param, str):
                            scope.define(
                                VariableDefinition(
                                    name=param,
                                    kind=DefinitionKind.PARAM,
                                    step_name=None,
                                )
                            )
                        elif isinstance(param, dict):
                            for pname in param:
                                scope.define(
                                    VariableDefinition(
                                        name=pname,
                                        kind=DefinitionKind.PARAM,
                                        step_name=None,
                                    )
                                )
                self._analyze_steps(wf_def.steps, scope, workflow_name=wf_name)

        return self.issues

    # -- Step list analysis ---------------------------------------------------

    def _analyze_steps(
        self, steps: List[Step], scope: Scope, workflow_name: str
    ) -> None:
        """Analyze a sequence of steps, defining variables as they are encountered."""
        for step in steps:
            self._analyze_step(step, scope, workflow_name)

    def _analyze_step(self, step: Step, scope: Scope, workflow_name: str) -> None:
        """Dispatch to the appropriate handler for the step body type."""
        body = step.body

        if isinstance(body, AssignStep):
            self._analyze_assign(body, scope, step.name, workflow_name)
        elif isinstance(body, CallStep):
            self._analyze_call(body, scope, step.name, workflow_name)
        elif isinstance(body, SwitchStep):
            self._analyze_switch(body, scope, step.name, workflow_name)
        elif isinstance(body, ForStep):
            self._analyze_for(body.for_body, scope, step.name, workflow_name)
        elif isinstance(body, TryStep):
            self._analyze_try(body, scope, step.name, workflow_name)
        elif isinstance(body, ParallelStep):
            self._analyze_parallel(body.parallel, scope, step.name, workflow_name)
        elif isinstance(body, ReturnStep):
            self._check_value_refs(body.return_value, scope, step.name, workflow_name)
        elif isinstance(body, RaiseStep):
            self._check_value_refs(body.raise_value, scope, step.name, workflow_name)
        elif isinstance(body, NestedStepsStep):
            # Nested steps share the same scope (not block-scoped)
            self._analyze_steps(body.steps, scope, workflow_name)

    # -- Specific step type handlers ------------------------------------------

    def _analyze_assign(
        self,
        assign: AssignStep,
        scope: Scope,
        step_name: str,
        workflow_name: str,
    ) -> None:
        """Process an assign step: check RHS refs, then define LHS variables."""
        for entry in assign.assign:
            for lhs, rhs in entry.items():
                # Check references in the RHS value
                self._check_value_refs(rhs, scope, step_name, workflow_name)
                # Define the variable (use root name -- before any dots/brackets)
                var_name = _root_var_name(lhs)
                scope.define(
                    VariableDefinition(
                        name=var_name,
                        kind=DefinitionKind.ASSIGN,
                        step_name=step_name,
                    )
                )

    def _analyze_call(
        self,
        call: CallStep,
        scope: Scope,
        step_name: str,
        workflow_name: str,
    ) -> None:
        """Process a call step: check args refs, then define result variable."""
        if call.args:
            self._check_value_refs(call.args, scope, step_name, workflow_name)
        if call.result:
            scope.define(
                VariableDefinition(
                    name=call.result,
                    kind=DefinitionKind.RESULT,
                    step_name=step_name,
                )
            )

    def _analyze_switch(
        self,
        switch: SwitchStep,
        scope: Scope,
        step_name: str,
        workflow_name: str,
    ) -> None:
        """Process a switch step.

        Variables defined inside switch branches are marked as 'maybe defined'
        since only one branch executes at runtime.
        """
        # Track variables defined in each branch
        branch_vars: List[Set[str]] = []

        for i, cond in enumerate(switch.switch):
            # Check condition expression
            self._check_value_refs(cond.condition, scope, step_name, workflow_name)

            branch_defined: Set[str] = set()

            # Check and collect variables from branch body
            if cond.assign:
                for entry in cond.assign:
                    for lhs, rhs in entry.items():
                        self._check_value_refs(rhs, scope, step_name, workflow_name)
                        branch_defined.add(_root_var_name(lhs))

            if cond.steps:
                branch_scope = scope.child(f"{step_name}/branch_{i}")
                self._analyze_steps(cond.steps, branch_scope, workflow_name)
                # Collect new definitions from branch scope
                branch_defined |= branch_scope._vars.keys()

            if cond.return_value is not None:
                self._check_value_refs(
                    cond.return_value, scope, step_name, workflow_name
                )
            if cond.raise_value is not None:
                self._check_value_refs(
                    cond.raise_value, scope, step_name, workflow_name
                )

            branch_vars.append(branch_defined)

        # Variables defined in ALL branches are 'definite'; others are 'maybe'
        if branch_vars:
            all_branches = set.intersection(*branch_vars) if branch_vars else set()
            any_branch = set.union(*branch_vars) if branch_vars else set()

            for var_name in any_branch:
                certainty = (
                    Certainty.DEFINITE if var_name in all_branches else Certainty.MAYBE
                )
                scope.define(
                    VariableDefinition(
                        name=var_name,
                        kind=DefinitionKind.ASSIGN,
                        certainty=certainty,
                        step_name=step_name,
                    )
                )

    def _analyze_for(
        self,
        for_body: ForBody,
        scope: Scope,
        step_name: str,
        workflow_name: str,
    ) -> None:
        """Process a for step: loop variables are loop-scoped."""
        # Check the 'in' or 'range' expression
        if for_body.in_value is not None:
            self._check_value_refs(for_body.in_value, scope, step_name, workflow_name)
        if for_body.range is not None:
            self._check_value_refs(for_body.range, scope, step_name, workflow_name)

        # Create child scope for loop variables
        loop_scope = scope.child(f"{step_name}/for")
        loop_scope.define(
            VariableDefinition(
                name=for_body.value,
                kind=DefinitionKind.FOR_VALUE,
                step_name=step_name,
            )
        )
        if for_body.index:
            loop_scope.define(
                VariableDefinition(
                    name=for_body.index,
                    kind=DefinitionKind.FOR_INDEX,
                    step_name=step_name,
                )
            )

        # Analyze loop body steps in loop scope
        self._analyze_steps(for_body.steps, loop_scope, workflow_name)

    def _analyze_try(
        self,
        try_step: TryStep,
        scope: Scope,
        step_name: str,
        workflow_name: str,
    ) -> None:
        """Process a try step."""
        try_body = try_step.try_body

        if isinstance(try_body, TryCallBody):
            if try_body.args:
                self._check_value_refs(try_body.args, scope, step_name, workflow_name)
            if try_body.result:
                scope.define(
                    VariableDefinition(
                        name=try_body.result,
                        kind=DefinitionKind.RESULT,
                        step_name=step_name,
                    )
                )
        elif isinstance(try_body, TryStepsBody):
            self._analyze_steps(try_body.steps, scope, workflow_name)

        # Except block: 'as' variable is scoped to the except block
        if try_step.except_body:
            except_scope = scope.child(f"{step_name}/except")
            except_scope.define(
                VariableDefinition(
                    name=try_step.except_body.as_value,
                    kind=DefinitionKind.EXCEPT_AS,
                    step_name=step_name,
                )
            )
            self._analyze_steps(try_step.except_body.steps, except_scope, workflow_name)

    def _analyze_parallel(
        self,
        parallel: ParallelBody,
        scope: Scope,
        step_name: str,
        workflow_name: str,
    ) -> None:
        """Process a parallel step.

        Branch variables are branch-local. Only 'shared' variables can be
        written across branches.
        """
        shared_vars = set(parallel.shared) if parallel.shared else set()

        if parallel.branches:
            for branch in parallel.branches:
                branch_scope = scope.child(f"{step_name}/branch/{branch.name}")
                # Shared variables are accessible in the branch
                self._analyze_steps(branch.steps, branch_scope, workflow_name)

        if parallel.for_body:
            self._analyze_for(parallel.for_body, scope, step_name, workflow_name)

    # -- Value reference checking ---------------------------------------------

    def _check_value_refs(
        self,
        value: Any,
        scope: Scope,
        step_name: str,
        workflow_name: str,
    ) -> None:
        """Check all expression references in a value tree."""
        expr_bodies = extract_expression_strings(value)
        for body in expr_bodies:
            refs = extract_variable_references(body)
            for ref in refs:
                # Skip subworkflow names (they're valid call targets)
                if ref in self._subworkflow_names:
                    continue
                defn = scope.lookup(ref)
                if defn is None:
                    self.issues.append(
                        VariableIssue(
                            severity=Severity.ERROR,
                            message=(f"Variable '{ref}' is referenced but not defined"),
                            variable=ref,
                            step_name=step_name,
                            workflow_name=workflow_name,
                        )
                    )
                elif defn.certainty == Certainty.MAYBE:
                    self.issues.append(
                        VariableIssue(
                            severity=Severity.WARNING,
                            message=(
                                f"Variable '{ref}' may not be defined "
                                f"(conditionally defined in step '{defn.step_name}')"
                            ),
                            variable=ref,
                            step_name=step_name,
                            workflow_name=workflow_name,
                        )
                    )


# =============================================================================
# Helpers
# =============================================================================


def _root_var_name(lhs: str) -> str:
    """Extract the root variable name from an assignment LHS.

    Examples:
        "x" -> "x"
        "config.key1" -> "config"
        'config["key1"]' -> "config"
        "items[0]" -> "items"
    """
    # Split on dot or bracket to get root name
    for i, ch in enumerate(lhs):
        if ch in (".", "["):
            return lhs[:i]
    return lhs


# =============================================================================
# Public API
# =============================================================================


def analyze_variables(workflow: Workflow) -> List[VariableIssue]:
    """Analyze a workflow for variable reference issues.

    Returns a list of VariableIssue objects (errors and warnings).
    """
    analyzer = VariableAnalyzer()
    return analyzer.analyze(workflow)
