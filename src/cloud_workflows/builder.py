"""Builder classes for constructing Cloud Workflows programmatically.

StepBuilder builds a list of steps via per-type method chaining:

    sb = (StepBuilder()
        .assign("init", x=10, y=20)
        .call("fetch", func="http.get", args={"url": url})
        .returns("done", value=expr("x + y")))

Workflow composes steps into SimpleWorkflow or SubworkflowsWorkflow.
Workflow extends StepBuilder so you can chain steps directly:

    # Simple workflow:
    w = Workflow().assign("init", x=10, y=20).returns("done", value=expr("x + y"))()

    # Multi-workflow with subworkflows:
    main = Subworkflow().assign("init", x=10).returns("done", value=expr("x"))
    helper = Subworkflow(params=["n"]).returns("done", value=expr("n"))
    w = Workflow({"main": main, "helper": helper})()

Write results to disk with build():

    build({"my_workflow.yaml": w})
"""

from __future__ import annotations

from pathlib import Path
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
    ExceptBody,
    ForStep,
    NestedStepsStep,
    ParallelStep,
    RaiseStep,
    RetryConfig,
    ReturnStep,
    SimpleWorkflow,
    Step,
    SubworkflowsWorkflow,
    SwitchStep,
    TryStep,
    Workflow as WorkflowModel,
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

# Type for steps= parameter: StepBuilder or lambda returning StepBuilder
_StepsInput = Union["StepBuilder", Callable[["StepBuilder"], Any]]

# Sentinel for distinguishing "not provided" from None
_MISSING = object()

__all__ = [
    "StepBuilder",
    "Workflow",
    "Subworkflow",
    "WorkflowBuilder",
    "build",
]


def _resolve_steps_input(steps: _StepsInput) -> "StepBuilder":
    """Resolve a _StepsInput to a StepBuilder instance."""
    if isinstance(steps, StepBuilder):
        return steps
    if callable(steps):
        sb = StepBuilder()
        steps(sb)
        return sb
    raise TypeError(f"Expected StepBuilder or callable, got {type(steps).__name__}")


# =============================================================================
# StepBuilder
# =============================================================================


class StepBuilder:
    """Builds a list of workflow steps via per-type method chaining.

    Each step type has its own method. Methods accept either keyword
    arguments for configuration, or a single callable (lambda configurator)
    that receives the corresponding sub-builder.

    Aliases are provided for methods that would otherwise require trailing
    underscores: ``returns``/``do_return``, ``raises``/``do_raise``,
    ``loop``, ``do_try``.

    Usage::

        sb = (StepBuilder()
            .assign("init", x=10, y=20)
            .call("fetch", func="http.get", args={"url": "..."})
            .switch("check", lambda sw: sw
                .condition(expr("x > 0"), next="positive")
                .condition(True, next="negative"))
            .returns("done", value=expr("x")))
    """

    def __init__(self) -> None:
        self._steps: List[Step] = []

    # -- helpers --------------------------------------------------------

    def _append(self, name: str, body: Any) -> StepBuilder:
        """Append a step with the given name and body."""
        self._steps.append(Step(name=name, body=cast(Any, body)))
        return self

    # -----------------------------------------------------------------
    # assign
    # -----------------------------------------------------------------

    def assign(
        self,
        name: str,
        configurator: Optional[Callable[[Assign], Any]] = None,
        /,
        **kwargs: Any,
    ) -> StepBuilder:
        """Add an assign step.

        Forms::

            # Shorthand kwargs — each kwarg becomes a variable assignment:
            .assign("init", x=10, y=20)

            # Explicit items list:
            .assign("init", items=[{"x": 10}, {"y": 20}])

            # Lambda configurator:
            .assign("init", lambda a: a.set("x", 10).set("y", 20))
        """
        builder = Assign()
        next_target = kwargs.pop("next", None)
        if configurator is not None and callable(configurator):
            configurator(builder)
        elif kwargs:
            if "items" in kwargs:
                builder.items(kwargs["items"])
            else:
                for k, v in kwargs.items():
                    builder.set(k, v)
        else:
            raise ValueError("assign requires kwargs or a lambda configurator")
        if next_target is not None:
            builder.next(next_target)
        return self._append(name, builder.build())

    # -----------------------------------------------------------------
    # call
    # -----------------------------------------------------------------

    def call(
        self,
        name: str,
        configurator: Optional[Callable[[Call], Any]] = None,
        /,
        *,
        func: Optional[str] = None,
        args: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
        next: Optional[str] = None,
    ) -> StepBuilder:
        """Add a call step.

        Forms::

            .call("fetch", func="http.get", args={"url": "..."}, result="resp")
            .call("fetch", lambda c: c.func("http.get").args(url="...").result("resp"))
        """
        builder = Call()
        if configurator is not None and callable(configurator):
            configurator(builder)
        else:
            if func is not None:
                builder.func(func)
            if args is not None:
                builder.args(**args)
            if result is not None:
                builder.result(result)
            if next is not None:
                builder.next(next)
            if func is None and configurator is None:
                raise ValueError("call requires 'func' kwarg or a lambda configurator")
        return self._append(name, builder.build())

    # -----------------------------------------------------------------
    # returns (primary) / return_ (backward compat)
    # -----------------------------------------------------------------

    def return_(
        self,
        name: str,
        configurator: Optional[Callable[[Return_], Any]] = None,
        /,
        *,
        value: Any = _MISSING,
    ) -> StepBuilder:
        """Add a return step.

        Preferred name: ``.returns()``.

        Forms::

            .returns("done", value=expr("x + y"))
            .returns("done", lambda r: r.value(expr("x + y")))
        """
        builder = Return_()
        if configurator is not None and callable(configurator):
            configurator(builder)
        elif value is not _MISSING:
            builder.value(value)
        else:
            raise ValueError(
                "returns() requires 'value' kwarg or a lambda configurator"
            )
        return self._append(name, builder.build())

    # -----------------------------------------------------------------
    # raises (primary) / raise_ (backward compat)
    # -----------------------------------------------------------------

    def raise_(
        self,
        name: str,
        configurator: Optional[Callable[[Raise_], Any]] = None,
        /,
        *,
        value: Any = _MISSING,
    ) -> StepBuilder:
        """Add a raise step.

        Preferred name: ``.raises()``.

        Forms::

            .raises("err", value="something went wrong")
            .raises("err", lambda r: r.value({"code": 404}))
        """
        builder = Raise_()
        if configurator is not None and callable(configurator):
            configurator(builder)
        elif value is not _MISSING:
            builder.value(value)
        else:
            raise ValueError("raises() requires 'value' kwarg or a lambda configurator")
        return self._append(name, builder.build())

    # -----------------------------------------------------------------
    # switch
    # -----------------------------------------------------------------

    def switch(
        self,
        name: str,
        configurator: Optional[Callable[[Switch], Any]] = None,
        /,
        *,
        conditions: Optional[List[Dict[str, Any]]] = None,
        next: Optional[str] = None,
    ) -> StepBuilder:
        """Add a switch step.

        Forms::

            .switch("check", conditions=[
                {"condition": expr("x > 0"), "next": "positive"},
                {"condition": True, "next": "negative"},
            ])
            .switch("check", lambda sw: sw
                .condition(expr("x > 0"), next="positive")
                .condition(True, next="negative"))
        """
        builder = Switch()
        if configurator is not None and callable(configurator):
            configurator(builder)
        elif conditions is not None:
            for cond in conditions:
                cond_copy = dict(cond)
                cond_value = cond_copy.pop("condition")
                builder.condition(cond_value, **cond_copy)
        else:
            raise ValueError(
                "switch requires 'conditions' kwarg or a lambda configurator"
            )
        if next is not None:
            builder.next(next)
        return self._append(name, builder.build())

    # -----------------------------------------------------------------
    # loop (primary) / for_ (backward compat)
    # -----------------------------------------------------------------

    def for_(
        self,
        name: str,
        configurator: Optional[Callable[[For], Any]] = None,
        /,
        *,
        value: Optional[str] = None,
        in_: Optional[Any] = None,
        range_: Optional[Any] = None,
        index: Optional[str] = None,
        steps: Optional[_StepsInput] = None,
    ) -> StepBuilder:
        """Add a for-loop step.

        Preferred name: ``.loop()``.

        Forms::

            .loop("loop", value="item", in_=["a", "b"],
                  steps=StepBuilder().call("log", func="sys.log"))
            .loop("loop", lambda f: f
                .value("item").items(["a", "b"])
                .steps(StepBuilder().call("log", func="sys.log")))
        """
        builder = For()
        if configurator is not None and callable(configurator):
            if value is not None:
                builder.value(value)
            configurator(builder)
        elif value is not None:
            builder.value(value)
            if in_ is not None:
                builder.items(in_)
            if range_ is not None:
                builder.range(range_)
            if index is not None:
                builder.index(index)
            if steps is not None:
                builder.steps(_resolve_steps_input(steps))
        else:
            raise ValueError("loop() requires kwargs or a lambda configurator")
        return self._append(name, builder.build())

    # -----------------------------------------------------------------
    # parallel
    # -----------------------------------------------------------------

    def parallel(
        self,
        name: str,
        configurator: Optional[Callable[[Parallel], Any]] = None,
        /,
        *,
        branches: Optional[Dict[str, _StepsInput]] = None,
        shared: Optional[List[str]] = None,
        exception_policy: Optional[str] = None,
        concurrency_limit: Optional[Union[int, str]] = None,
    ) -> StepBuilder:
        """Add a parallel step.

        Forms::

            .parallel("p", branches={
                "b1": StepBuilder().assign("s", x=1),
                "b2": StepBuilder().assign("s", y=2),
            })
            .parallel("p", lambda p: p
                .branch("b1", StepBuilder().assign("s", x=1))
                .branch("b2", StepBuilder().assign("s", y=2)))
        """
        builder = Parallel()
        if configurator is not None and callable(configurator):
            configurator(builder)
        elif branches is not None:
            for branch_name, branch_steps in branches.items():
                builder.branch(branch_name, _resolve_steps_input(branch_steps))
        else:
            raise ValueError(
                "parallel requires 'branches' kwarg or a lambda configurator"
            )
        if shared is not None:
            builder.shared(shared)
        if exception_policy is not None:
            builder.exception_policy(exception_policy)
        if concurrency_limit is not None:
            builder.concurrency_limit(concurrency_limit)
        return self._append(name, builder.build())

    # -----------------------------------------------------------------
    # do_try (primary) / try_ (backward compat)
    # -----------------------------------------------------------------

    def try_(
        self,
        name: str,
        configurator: Optional[Callable[[Try_], Any]] = None,
        /,
        *,
        body: Optional[_StepsInput] = None,
        retry: Optional[Union[Dict[str, Any], RetryConfig, str]] = None,
        except_: Optional[Union[Dict[str, Any], ExceptBody]] = None,
    ) -> StepBuilder:
        """Add a try/retry/except step.

        Preferred name: ``.do_try()``.

        Forms::

            .do_try("t", body=StepBuilder().call("f", func="may_fail"),
                    retry={"predicate": "http.default_retry", "max_retries": 3})
            .do_try("t", lambda t: t
                .body(StepBuilder().call("f", func="may_fail"))
                .retry(predicate="http.default_retry", max_retries=3)
                .exception(error="e", steps=except_builder))
        """
        builder = Try_()
        if configurator is not None and callable(configurator):
            configurator(builder)
        elif body is not None:
            builder.body(_resolve_steps_input(body))
            if retry is not None:
                if isinstance(retry, dict):
                    builder.retry(**retry)
                else:
                    # RetryConfig or string predicate — store directly
                    builder._state["retry"] = retry  # noqa: SLF001
            if except_ is not None:
                if isinstance(except_, dict):
                    # Map old-style as_ to new error param
                    mapped = {}
                    for k, v in except_.items():
                        mapped["error" if k == "as_" else k] = v
                    builder.exception(**mapped)
        else:
            raise ValueError("do_try() requires 'body' kwarg or a lambda configurator")
        return self._append(name, builder.build())

    # -----------------------------------------------------------------
    # nested_steps (steps within steps)
    # -----------------------------------------------------------------

    def nested_steps(
        self,
        name: str,
        configurator: Optional[Callable[[Steps], Any]] = None,
        /,
        *,
        body: Optional[_StepsInput] = None,
        next: Optional[str] = None,
    ) -> StepBuilder:
        """Add a nested steps step.

        Forms::

            .nested_steps("block", body=StepBuilder().assign("s", x=1), next="end")
            .nested_steps("block", lambda s: s.body(sb).next("end"))
        """
        builder = Steps()
        if configurator is not None and callable(configurator):
            configurator(builder)
        elif body is not None:
            builder.body(_resolve_steps_input(body))
        else:
            raise ValueError(
                "nested_steps requires 'body' kwarg or a lambda configurator"
            )
        if next is not None:
            builder.next(next)
        return self._append(name, builder.build())

    # -----------------------------------------------------------------
    # raw passthrough (dict, Pydantic model, or sub-builder)
    # -----------------------------------------------------------------

    def raw(self, name: str, body: Any) -> StepBuilder:
        """Add a step from a raw dict, Pydantic model, or sub-builder.

        This is the escape hatch for passing pre-built step bodies directly::

            .raw("init", AssignStep(assign=[{"x": 10}]))
            .raw("init", {"assign": [{"x": 10}]})
            .raw("init", Assign().set("x", 10))
        """
        if isinstance(body, _SUB_BUILDERS):
            return self._append(name, body.build())
        if isinstance(body, _STEP_MODELS):
            return self._append(name, body)
        if isinstance(body, dict):
            return self._append(name, body)
        raise TypeError(
            f"raw() body must be a dict, Pydantic model, or sub-builder, "
            f"got {type(body).__name__}"
        )

    # -----------------------------------------------------------------
    # apply (merge steps from another builder)
    # -----------------------------------------------------------------

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
                f"apply() requires a StepBuilder instance, got {type(source).__name__}"
            )
        self._steps.extend(source._steps)
        return self

    # -----------------------------------------------------------------
    # build
    # -----------------------------------------------------------------

    def build(self) -> List[Step]:
        """Return the list of Step objects."""
        return list(self._steps)

    # -----------------------------------------------------------------
    # Preferred names (aliases that avoid trailing underscores)
    # -----------------------------------------------------------------

    #: Preferred name for :meth:`return_`.
    returns = return_
    #: Alternative alias for :meth:`return_`.
    do_return = return_
    #: Preferred name for :meth:`raise_`.
    raises = raise_
    #: Alternative alias for :meth:`raise_`.
    do_raise = raise_
    #: Preferred name for :meth:`for_`.
    loop = for_
    #: Preferred name for :meth:`try_`.
    do_try = try_


# =============================================================================
# Subworkflow — StepBuilder with params
# =============================================================================


class Subworkflow(StepBuilder):
    """A named workflow definition with optional parameters.

    Extends StepBuilder, so steps can be chained directly::

        helper = (Subworkflow(params=["person"])
            .assign("build", greeting=expr('"Hello, " + person'))
            .returns("done", value=expr("greeting")))

    Used as a value in the dict passed to :class:`Workflow`.
    """

    def __init__(
        self,
        *,
        params: Optional[List[Union[str, Dict[str, Any]]]] = None,
    ) -> None:
        super().__init__()
        self._params = params


# =============================================================================
# Workflow — entry point for building workflows
# =============================================================================


class Workflow(StepBuilder):
    """Build a Cloud Workflow, either as a simple step chain or multi-workflow.

    **Simple workflow** — chain steps directly, then call the instance::

        w = Workflow().assign("init", x=10, y=20).returns("done", value=expr("x + y"))()

    **Multi-workflow** — pass a dict of name -> Subworkflow::

        main = Subworkflow().assign("init", x=10).returns("done", value=expr("x"))
        helper = Subworkflow(params=["n"]).returns("done", value=expr("n"))
        w = Workflow({"main": main, "helper": helper})()

    Calling the instance (or ``.build()``) returns :class:`SimpleWorkflow`
    when there is a single "main" with no params, otherwise
    :class:`SubworkflowsWorkflow`.
    """

    def __init__(
        self,
        workflows: Optional[Dict[str, Subworkflow]] = None,
    ) -> None:
        super().__init__()
        self._workflows: Dict[str, Subworkflow] = dict(workflows) if workflows else {}

    def build(  # type: ignore[override]
        self,
    ) -> Union[SimpleWorkflow, SubworkflowsWorkflow]:
        """Finalize and return the constructed workflow.

        If this Workflow has steps chained on it (and no sub-workflows dict),
        it builds a SimpleWorkflow from those steps.

        If a sub-workflows dict was provided, it builds from those.

        Returns:
            SimpleWorkflow or SubworkflowsWorkflow.

        Raises:
            ValueError: If no steps/workflows were defined.
        """
        # Determine sources
        has_inline_steps = len(self._steps) > 0
        has_workflows = len(self._workflows) > 0

        if not has_inline_steps and not has_workflows:
            raise ValueError(
                "No steps or workflows defined — chain steps or pass "
                "a dict of Subworkflow instances"
            )

        if has_inline_steps and has_workflows:
            raise ValueError(
                "Cannot both chain steps on Workflow and pass a workflows dict"
            )

        if has_inline_steps:
            # Simple mode: this Workflow IS the step chain
            return SimpleWorkflow(steps=list(self._steps))

        # Multi-workflow mode
        # Validate all workflows have steps
        for wf_name, wf in self._workflows.items():
            if not wf._steps:
                raise ValueError(f"Workflow '{wf_name}' has no steps")

        # Single 'main' without params -> SimpleWorkflow
        if len(self._workflows) == 1 and "main" in self._workflows:
            main_wf = self._workflows["main"]
            if main_wf._params is None:
                return SimpleWorkflow(steps=list(main_wf._steps))

        # Everything else -> SubworkflowsWorkflow
        workflows: Dict[str, WorkflowDefinition] = {}
        for wf_name, wf in self._workflows.items():
            workflows[wf_name] = WorkflowDefinition(
                params=wf._params,
                steps=list(wf._steps),
            )
        return SubworkflowsWorkflow(workflows=workflows)

    def __call__(self) -> Union[SimpleWorkflow, SubworkflowsWorkflow]:
        """Finalize the workflow. Same as ``.build()``.

        Example::

            w = Workflow().assign("init", x=10).returns("done", value=expr("x"))()
        """
        return self.build()


# =============================================================================
# WorkflowBuilder (backward-compatible, wraps Workflow/Subworkflow)
# =============================================================================


class WorkflowBuilder:
    """Composes StepBuilder(s) into SimpleWorkflow or SubworkflowsWorkflow.

    .. deprecated::
        Use :class:`Workflow` and :class:`Subworkflow` instead.
        ``WorkflowBuilder`` is retained for backward compatibility.

    Usage::

        # Single main workflow (shorthand):
        w = WorkflowBuilder().steps(sb).build()

        # Multiple workflows / subworkflows:
        w = (WorkflowBuilder()
            .workflow("main", main_sb)
            .workflow("helper", helper_sb, params=["n"])
            .build())
    """

    def __init__(self) -> None:
        self._workflows: Dict[
            str, tuple[Optional[List[Union[str, Dict[str, Any]]]], List[Step]]
        ] = {}

    def steps(self, steps: _StepsInput) -> WorkflowBuilder:
        """Shorthand: define the 'main' workflow without params.

        Equivalent to ``.workflow("main", steps)``.

        Args:
            steps: A StepBuilder instance or a callable that configures one.
        """
        return self.workflow("main", steps)

    def workflow(
        self,
        name: str,
        steps: _StepsInput,
        *,
        params: Optional[List[Union[str, Dict[str, Any]]]] = None,
    ) -> WorkflowBuilder:
        """Add a named workflow definition.

        Args:
            name: Workflow name (e.g. "main", "helper").
            steps: A StepBuilder instance or a callable that configures one.
            params: Optional parameter list for the workflow.

        Returns:
            self, for chaining.
        """
        if name in self._workflows:
            raise ValueError(f"Duplicate workflow name: '{name}'")

        sb = _resolve_steps_input(steps)
        step_list = sb.build()
        self._workflows[name] = (params, step_list)
        return self

    def build(self) -> Union[SimpleWorkflow, SubworkflowsWorkflow]:
        """Finalize and return the constructed workflow.

        Returns:
            SimpleWorkflow if there is exactly one workflow named "main"
            with no params. SubworkflowsWorkflow otherwise.

        Raises:
            ValueError: If no workflows were defined or any workflow has
                no steps.
        """
        if not self._workflows:
            raise ValueError(
                "No workflows defined — call .workflow() or .steps() first"
            )

        # Validate all workflows have steps
        for wf_name, (_, wf_steps) in self._workflows.items():
            if not wf_steps:
                raise ValueError(f"Workflow '{wf_name}' has no steps")

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


# =============================================================================
# build() — write workflow definitions to YAML files
# =============================================================================


def build(
    workflows: Dict[str, Union[WorkflowModel, Workflow]],
    output_dir: Union[str, Path] = ".",
) -> List[Path]:
    """Build workflow definitions and write them to YAML files.

    ``workflows`` is a dict mapping filenames to workflow objects. Values
    can be finalized models (``SimpleWorkflow`` / ``SubworkflowsWorkflow``)
    or unfinalized ``Workflow`` builder instances (which are automatically
    finalized by calling them).

    Args:
        workflows: Dict of ``{filename: workflow}``.  Filenames are relative
            paths (e.g. ``"my_flow.yaml"``).
        output_dir: Directory to write files into. Defaults to the current
            working directory. Created automatically if it does not exist.

    Returns:
        List of ``Path`` objects for every file that was written.

    Raises:
        TypeError: If any value is not a workflow model or Workflow builder.
        ValueError: If the workflows dict is empty.

    Example::

        from cloud_workflows import Workflow, build, expr

        build({
            "my_workflow.yaml": Workflow()
                .assign("init", x=10, y=20)
                .returns("done", value=expr("x + y")),
        })
    """
    if not workflows:
        raise ValueError("workflows must not be empty")

    if not isinstance(workflows, dict):
        raise TypeError(f"workflows must be a dict, got {type(workflows).__name__}")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []
    for filename, workflow in workflows.items():
        if not isinstance(filename, str):
            raise TypeError(
                f"Workflow filename must be a string, got {type(filename).__name__}"
            )

        # Auto-finalize Workflow builder instances
        if isinstance(workflow, Workflow):
            workflow = workflow()

        if not isinstance(workflow, (SimpleWorkflow, SubworkflowsWorkflow)):
            raise TypeError(
                f"Workflow value must be SimpleWorkflow, SubworkflowsWorkflow, "
                f"or Workflow builder, got {type(workflow).__name__}"
            )

        path = out / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(workflow.to_yaml(), encoding="utf-8")
        written.append(path)

    return written
