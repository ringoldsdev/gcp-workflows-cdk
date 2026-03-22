"""StepBuilder and WorkflowBuilder for constructing Cloud Workflows programmatically.

StepBuilder builds a list of steps via .step() chaining. Each step type is
dispatched via a match statement on the type string. Three input forms:

1. String type + kwargs:  step("init", "assign", x=10, y=20)
2. String type + lambda:  step("init", "assign", lambda a: a.set("x", 10))
3. Model/dict passthrough: step("init", AssignStep(assign=[{"x": 10}]))

WorkflowBuilder composes StepBuilder(s) into SimpleWorkflow or SubworkflowsWorkflow.

Usage:
    from cloud_workflows import StepBuilder, WorkflowBuilder, expr

    main = (StepBuilder()
        .step("init", "assign", x=10, y=20)
        .step("done", "return", value=expr("x + y")))

    workflow = WorkflowBuilder().workflow("main", main).build()
    print(workflow.to_yaml())
"""

from __future__ import annotations

from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Union,
    cast,
)

from .models import (
    AssignStep,
    CallStep,
    ForStep,
    NestedStepsStep,
    ParallelStep,
    RaiseStep,
    ReturnStep,
    SimpleWorkflow,
    Step,
    SubworkflowsWorkflow,
    SwitchStep,
    TryStep,
    WorkflowDefinition,
)
from .steps import (
    Assign,
    Call,
    For,
    Parallel,
    Raise_,
    Return_,
    Steps,
    Switch,
    Try_,
)

__all__ = [
    "StepBuilder",
    "WorkflowBuilder",
]

# All Pydantic step model types for isinstance checks
_STEP_MODELS = (
    AssignStep,
    CallStep,
    ReturnStep,
    RaiseStep,
    SwitchStep,
    ForStep,
    ParallelStep,
    TryStep,
    NestedStepsStep,
)

# All sub-builder types for isinstance checks
_SUB_BUILDERS = (Assign, Call, Return_, Raise_, Switch, For, Parallel, Try_, Steps)


# =============================================================================
# StepBuilder
# =============================================================================


class StepBuilder:
    """Builds a list of workflow steps via .step() chaining.

    Supports three input forms for step bodies:
    1. String type + kwargs: step("id", "assign", x=10)
    2. String type + lambda: step("id", "assign", lambda a: a.set("x", 10))
    3. Passthrough: step("id", AssignStep(...)) or step("id", {"assign": [...]})

    Also supports sub-builder instances: step("id", Assign().set("x", 10))
    """

    def __init__(self) -> None:
        self._steps: List[Step] = []

    def step(
        self,
        name: str,
        type_or_body: Any,
        configurator: Any = None,
        **kwargs: Any,
    ) -> StepBuilder:
        """Add a step.

        Args:
            name: Step identifier.
            type_or_body: A string type name ("assign", "call", etc.),
                a Pydantic model instance, a dict, or a sub-builder instance.
            configurator: Optional callable (lambda) for configuring sub-builders.
                Only used when type_or_body is a string. If not callable,
                treated as part of kwargs dispatch.
            **kwargs: Additional keyword arguments for string-type dispatch.

        Returns:
            self, for chaining.
        """
        body = self._resolve_body(type_or_body, configurator, kwargs)
        self._steps.append(Step(name=name, body=cast(Any, body)))
        return self

    def apply(
        self,
        source: Union[StepBuilder, Callable[[], Optional[StepBuilder]]],
    ) -> StepBuilder:
        """Merge steps from another StepBuilder into this one.

        Args:
            source: A StepBuilder instance, or a no-arg callable returning
                StepBuilder or None. If None is returned, nothing happens.

        Returns:
            self, for chaining.
        """
        if callable(source) and not isinstance(source, StepBuilder):
            result = source()
            if result is None:
                return self
            source = result
        if not isinstance(source, StepBuilder):
            raise TypeError(
                f"StepBuilder.apply() requires a StepBuilder instance, got {type(source).__name__}"
            )
        self._steps.extend(source._steps)
        return self

    def build(self) -> List[Step]:
        """Return the list of Step objects."""
        return list(self._steps)

    def _resolve_body(
        self,
        type_or_body: Any,
        configurator: Any,
        kwargs: Dict[str, Any],
    ) -> Any:
        """Resolve the step body from the various input forms."""
        # Sub-builder instance passed directly
        if isinstance(type_or_body, _SUB_BUILDERS):
            return type_or_body.build()

        # Pydantic model passthrough
        if isinstance(type_or_body, _STEP_MODELS):
            return type_or_body

        # Dict passthrough
        if isinstance(type_or_body, dict):
            return type_or_body

        # String type dispatch
        if isinstance(type_or_body, str):
            return self._dispatch_string_type(type_or_body, configurator, kwargs)

        raise TypeError(
            f"step() type_or_body must be a string, dict, Pydantic model, "
            f"or sub-builder, got {type(type_or_body).__name__}"
        )

    def _dispatch_string_type(
        self,
        step_type: str,
        configurator: Any,
        kwargs: Dict[str, Any],
    ) -> Any:
        """Dispatch string step types to sub-builders via match."""
        is_lambda = callable(configurator)

        match step_type:
            case "assign":
                return self._build_assign(is_lambda, configurator, kwargs)
            case "call":
                return self._build_call(is_lambda, configurator, kwargs)
            case "return":
                return self._build_return(is_lambda, configurator, kwargs)
            case "raise":
                return self._build_raise(is_lambda, configurator, kwargs)
            case "switch":
                return self._build_switch(is_lambda, configurator, kwargs)
            case "for":
                return self._build_for(is_lambda, configurator, kwargs)
            case "parallel":
                return self._build_parallel(is_lambda, configurator, kwargs)
            case "try":
                return self._build_try(is_lambda, configurator, kwargs)
            case "steps":
                return self._build_steps(is_lambda, configurator, kwargs)
            case _:
                raise ValueError(f"Unknown step type: '{step_type}'")

    # -- Individual type builders --

    def _build_assign(
        self, is_lambda: bool, configurator: Any, kwargs: Dict[str, Any]
    ) -> AssignStep:
        builder = Assign()
        if is_lambda:
            configurator(builder)
        elif kwargs:
            if "items" in kwargs:
                builder.items(kwargs["items"])
            else:
                for k, v in kwargs.items():
                    if k == "next":
                        builder.next(v)
                    else:
                        builder.set(k, v)
        else:
            raise ValueError("assign step requires kwargs or a lambda configurator")
        return builder.build()

    def _build_call(
        self, is_lambda: bool, configurator: Any, kwargs: Dict[str, Any]
    ) -> CallStep:
        builder = Call()
        if is_lambda:
            configurator(builder)
        elif kwargs:
            if "func" in kwargs:
                builder.func(kwargs["func"])
            if "args" in kwargs:
                builder.args(**kwargs["args"])
            if "result" in kwargs:
                builder.result(kwargs["result"])
            if "next" in kwargs:
                builder.next(kwargs["next"])
        else:
            raise ValueError("call step requires kwargs or a lambda configurator")
        return builder.build()

    def _build_return(
        self, is_lambda: bool, configurator: Any, kwargs: Dict[str, Any]
    ) -> ReturnStep:
        builder = Return_()
        if is_lambda:
            configurator(builder)
        elif "value" in kwargs:
            builder.value(kwargs["value"])
        else:
            raise ValueError(
                "return step requires 'value' kwarg or a lambda configurator"
            )
        return builder.build()

    def _build_raise(
        self, is_lambda: bool, configurator: Any, kwargs: Dict[str, Any]
    ) -> RaiseStep:
        builder = Raise_()
        if is_lambda:
            configurator(builder)
        elif "value" in kwargs:
            builder.value(kwargs["value"])
        else:
            raise ValueError(
                "raise step requires 'value' kwarg or a lambda configurator"
            )
        return builder.build()

    def _build_switch(
        self, is_lambda: bool, configurator: Any, kwargs: Dict[str, Any]
    ) -> SwitchStep:
        builder = Switch()
        if is_lambda:
            configurator(builder)
        elif "conditions" in kwargs:
            for cond in kwargs["conditions"]:
                cond_copy = dict(cond)
                cond_value = cond_copy.pop("condition")
                builder.condition(cond_value, **cond_copy)
            if "next" in kwargs:
                builder.next(kwargs["next"])
        else:
            raise ValueError(
                "switch step requires 'conditions' kwarg or a lambda configurator"
            )
        return builder.build()

    def _build_for(
        self, is_lambda: bool, configurator: Any, kwargs: Dict[str, Any]
    ) -> ForStep:
        builder = For()
        if is_lambda:
            # For lambda, 'value' must come from kwargs since For() needs it
            if "value" in kwargs:
                builder.value(kwargs["value"])
            configurator(builder)
        elif kwargs:
            if "value" in kwargs:
                builder.value(kwargs["value"])
            if "in_" in kwargs:
                builder.in_(kwargs["in_"])
            if "range_" in kwargs:
                builder.range_(kwargs["range_"])
            if "index" in kwargs:
                builder.index(kwargs["index"])
            if "steps" in kwargs:
                builder.steps(kwargs["steps"])
        else:
            raise ValueError("for step requires kwargs or a lambda configurator")
        return builder.build()

    def _build_parallel(
        self, is_lambda: bool, configurator: Any, kwargs: Dict[str, Any]
    ) -> ParallelStep:
        builder = Parallel()
        if is_lambda:
            configurator(builder)
        elif "branches" in kwargs:
            branches = kwargs["branches"]
            if isinstance(branches, dict):
                for name, steps in branches.items():
                    builder.branch(name, steps)
            else:
                raise ValueError(
                    "parallel 'branches' must be a dict of {name: StepBuilder}"
                )
            if "shared" in kwargs:
                builder.shared(kwargs["shared"])
            if "exception_policy" in kwargs:
                builder.exception_policy(kwargs["exception_policy"])
            if "concurrency_limit" in kwargs:
                builder.concurrency_limit(kwargs["concurrency_limit"])
        else:
            raise ValueError(
                "parallel step requires 'branches' kwarg or a lambda configurator"
            )
        return builder.build()

    def _build_try(
        self, is_lambda: bool, configurator: Any, kwargs: Dict[str, Any]
    ) -> TryStep:
        builder = Try_()
        if is_lambda:
            configurator(builder)
        elif kwargs:
            if "body" in kwargs:
                builder.body(kwargs["body"])
            if "retry" in kwargs:
                retry = kwargs["retry"]
                if isinstance(retry, dict):
                    builder.retry(**retry)
                else:
                    builder._retry = retry
            if "except_" in kwargs:
                exc = kwargs["except_"]
                if isinstance(exc, dict):
                    builder.except_(**exc)
        else:
            raise ValueError("try step requires kwargs or a lambda configurator")
        return builder.build()

    def _build_steps(
        self, is_lambda: bool, configurator: Any, kwargs: Dict[str, Any]
    ) -> NestedStepsStep:
        builder = Steps()
        if is_lambda:
            configurator(builder)
        elif kwargs:
            if "body" in kwargs:
                builder.body(kwargs["body"])
            if "next" in kwargs:
                builder.next(kwargs["next"])
        else:
            raise ValueError("steps step requires kwargs or a lambda configurator")
        return builder.build()


# =============================================================================
# WorkflowBuilder
# =============================================================================


class WorkflowBuilder:
    """Composes StepBuilder(s) into SimpleWorkflow or SubworkflowsWorkflow.

    Usage:
        # Simple (single 'main' workflow without params):
        w = WorkflowBuilder().workflow("main", step_builder).build()

        # Subworkflows:
        w = (WorkflowBuilder()
            .workflow("main", main_steps)
            .workflow("helper", helper_steps, params=["n"])
            .build())
    """

    def __init__(self) -> None:
        self._workflows: Dict[
            str, tuple[Optional[List[Union[str, Dict[str, Any]]]], List[Step]]
        ] = {}

    def workflow(
        self,
        name: str,
        steps: StepBuilder,
        *,
        params: Optional[List[Union[str, Dict[str, Any]]]] = None,
    ) -> WorkflowBuilder:
        """Add a workflow definition.

        Args:
            name: Workflow name (e.g. "main", "helper").
            steps: A StepBuilder containing the workflow's steps.
            params: Optional parameter list for the workflow.

        Returns:
            self, for chaining.
        """
        if name in self._workflows:
            raise ValueError(f"Duplicate workflow name: '{name}'")

        step_list = steps.build()
        self._workflows[name] = (params, step_list)
        return self

    def build(self) -> Union[SimpleWorkflow, SubworkflowsWorkflow]:
        """Finalize and return the constructed workflow.

        Returns:
            SimpleWorkflow if there is exactly one workflow named "main" with no params.
            SubworkflowsWorkflow otherwise.

        Raises:
            ValueError: If no workflows were defined or any workflow has no steps.
        """
        if not self._workflows:
            raise ValueError("No workflows defined — call .workflow() first")

        # Validate all workflows have steps
        for wf_name, (_, wf_steps) in self._workflows.items():
            if not wf_steps:
                raise ValueError(
                    f"Workflow '{wf_name}' has no steps — add at least one .step()"
                )

        # Single 'main' workflow without params → SimpleWorkflow
        if len(self._workflows) == 1 and "main" in self._workflows:
            params, steps = self._workflows["main"]
            if params is None:
                return SimpleWorkflow(steps=steps)

        # Everything else → SubworkflowsWorkflow
        workflows: Dict[str, WorkflowDefinition] = {}
        for wf_name, (wf_params, wf_steps) in self._workflows.items():
            workflows[wf_name] = WorkflowDefinition(
                params=wf_params,
                steps=wf_steps,
            )
        return SubworkflowsWorkflow(workflows=workflows)
