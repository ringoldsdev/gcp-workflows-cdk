"""StepBuilder and WorkflowBuilder for constructing Cloud Workflows programmatically.

StepBuilder builds a list of steps via per-type method chaining. Each step
type has its own method that accepts either kwargs or a lambda configurator:

    sb = (StepBuilder()
        .assign("init", x=10, y=20)
        .call("fetch", func="http.get", args={"url": url})
        .return_("done", value=expr("x + y")))

WorkflowBuilder composes StepBuilder(s) into SimpleWorkflow or SubworkflowsWorkflow:

    # Single main workflow (shorthand):
    w = WorkflowBuilder().steps(sb).build()

    # Multiple workflows:
    w = (WorkflowBuilder()
        .workflow("main", sb)
        .workflow("helper", sb2, params=["n"])
        .build())

Write results to disk with build():

    build([("my_workflow.yaml", w)])
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
    Workflow,
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

    Usage::

        sb = (StepBuilder()
            .assign("init", x=10, y=20)
            .call("fetch", func="http.get", args={"url": "..."})
            .switch("check", lambda sw: sw
                .condition(expr("x > 0"), next="positive")
                .condition(True, next="negative"))
            .return_("done", value=expr("x")))
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
    # return_
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

        Forms::

            .return_("done", value=expr("x + y"))
            .return_("done", lambda r: r.value(expr("x + y")))
        """
        builder = Return_()
        if configurator is not None and callable(configurator):
            configurator(builder)
        elif value is not _MISSING:
            builder.value(value)
        else:
            raise ValueError("return_ requires 'value' kwarg or a lambda configurator")
        return self._append(name, builder.build())

    # -----------------------------------------------------------------
    # raise_
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

        Forms::

            .raise_("err", value="something went wrong")
            .raise_("err", lambda r: r.value({"code": 404}))
        """
        builder = Raise_()
        if configurator is not None and callable(configurator):
            configurator(builder)
        elif value is not _MISSING:
            builder.value(value)
        else:
            raise ValueError("raise_ requires 'value' kwarg or a lambda configurator")
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
    # for_
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

        Forms::

            .for_("loop", value="item", in_=["a", "b"],
                  steps=StepBuilder().call("log", func="sys.log"))
            .for_("loop", value="item", in_=items,
                  steps=lambda s: s.call("log", func="sys.log"))
            .for_("loop", lambda f: f
                .value("item").in_(["a", "b"])
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
                builder.in_(in_)
            if range_ is not None:
                builder.range_(range_)
            if index is not None:
                builder.index(index)
            if steps is not None:
                builder.steps(_resolve_steps_input(steps))
        else:
            raise ValueError("for_ requires kwargs or a lambda configurator")
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
    # try_
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

        Forms::

            .try_("t", body=StepBuilder().call("f", func="may_fail"),
                  retry={"predicate": "http.default_retry", "max_retries": 3})
            .try_("t", lambda t: t
                .body(StepBuilder().call("f", func="may_fail"))
                .retry(predicate="http.default_retry", max_retries=3))
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
                    builder._retry = retry  # noqa: SLF001
            if except_ is not None:
                if isinstance(except_, dict):
                    builder.except_(**except_)
        else:
            raise ValueError("try_ requires 'body' kwarg or a lambda configurator")
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


# =============================================================================
# WorkflowBuilder
# =============================================================================


class WorkflowBuilder:
    """Composes StepBuilder(s) into SimpleWorkflow or SubworkflowsWorkflow.

    Usage::

        # Single main workflow (shorthand):
        w = WorkflowBuilder().steps(sb).build()
        w = WorkflowBuilder().steps(lambda s: s.assign("init", x=10)).build()

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
    workflows: List[tuple[str, Workflow]],
    output_dir: Union[str, Path] = ".",
) -> List[Path]:
    """Build workflow definitions and write them to YAML files.

    Each entry in ``workflows`` is a ``(filename, workflow)`` tuple where
    *filename* is a relative path (e.g. ``"my_flow.yaml"``) and *workflow*
    is a ``SimpleWorkflow`` or ``SubworkflowsWorkflow`` instance — typically
    produced by ``WorkflowBuilder.build()``.

    Args:
        workflows: List of ``(filename, workflow)`` pairs.
        output_dir: Directory to write files into. Defaults to the current
            working directory. Created automatically if it does not exist.

    Returns:
        List of ``Path`` objects for every file that was written.

    Raises:
        TypeError: If any entry is not a valid ``(str, Workflow)`` tuple.
        ValueError: If the workflows list is empty.

    Example::

        from cloud_workflows import StepBuilder, WorkflowBuilder, build, expr

        main = (StepBuilder()
            .assign("init", x=10, y=20)
            .return_("done", value=expr("x + y")))

        build([
            ("my_workflow.yaml", WorkflowBuilder().steps(main).build()),
        ])
    """
    if not workflows:
        raise ValueError("workflows list must not be empty")

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    written: List[Path] = []
    for entry in workflows:
        if (
            not isinstance(entry, tuple)
            or len(entry) != 2
            or not isinstance(entry[0], str)
        ):
            raise TypeError(
                f"Each entry must be a (str, Workflow) tuple, got {type(entry).__name__}"
            )

        filename, workflow = entry
        if not isinstance(workflow, (SimpleWorkflow, SubworkflowsWorkflow)):
            raise TypeError(
                f"Workflow must be SimpleWorkflow or SubworkflowsWorkflow, "
                f"got {type(workflow).__name__}"
            )

        path = out / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(workflow.to_yaml(), encoding="utf-8")
        written.append(path)

    return written
