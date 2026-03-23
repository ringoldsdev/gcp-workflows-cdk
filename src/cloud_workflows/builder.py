"""Steps container and build() function for Cloud Workflows CDK.

``Steps`` is the universal container for workflow steps.  Steps are added
via convenience methods that mirror each step type::

    s = (Steps()
        .assign("init", x=10, y=20)
        .call("log", "sys.log", args={"text": expr("x")})
        .returns("done", expr("x + y")))

For full control you can also use the generic ``.step()`` method::

    s.step("init", Assign(x=10, y=20))

``Steps`` instances are composable — merging steps from another container::

    common = Steps()
    common.call("log", "sys.log", args={"text": "starting"})

    main = Steps()
    main.merge(common)
    main.returns("done", "ok")

For subworkflows with parameters, pass ``params`` to the constructor::

    helper = Steps(params=["input", {"timeout": 30}])
    helper.call("log", "sys.log", args={"text": expr("input")})
    helper.returns("done", "ok")

Write to disk with ``build()``::

    build({"workflow.yaml": {"main": main}})

``build()`` always requires a ``dict[str, Steps]`` with a ``"main"`` key
for each file entry.
"""

from __future__ import annotations

from pathlib import Path
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
)

from .models import (
    SimpleWorkflow,
    SubworkflowsWorkflow,
    Workflow as WorkflowModel,
    WorkflowDefinition,
)
from .steps import (
    StepType,
    Assign as _Assign,
    Call as _Call,
    Return as _Return,
    Raise as _Raise,
    Switch as _Switch,
    Condition,
    For as _For,
    Parallel as _Parallel,
    Try as _Try,
    NestedSteps as _NestedSteps,
)
from .retry import Retry

__all__ = [
    "Steps",
    "build",
]


# =============================================================================
# Steps — universal step container
# =============================================================================


class Steps:
    """Universal container for workflow steps.

    The preferred API uses convenience alias methods that mirror each
    step type::

        s = (Steps()
            .assign("init", x=10, y=20)
            .call("log", "sys.log", args={"text": expr("x")})
            .returns("done", expr("x + y")))

    For full control, the generic ``.step()`` method accepts any
    ``StepType`` instance::

        s.step("init", Assign(x=10, y=20))

    Merge steps from another container via ``.merge()``::

        s.merge(other_steps)

    Optional ``params`` makes this container a subworkflow with parameters.

    Args:
        params: Optional list of parameter names (strings) or parameter
            dicts with defaults (e.g. ``[{"timeout": 30}]``).
    """

    def __init__(
        self,
        *,
        params: Optional[List[Union[str, Dict[str, Any]]]] = None,
    ) -> None:
        self._steps: List[tuple[str, StepType]] = []
        self._params = params

    def step(self, step_id: str, step: StepType) -> "Steps":
        """Add a named step and return ``self`` for chaining.

        Args:
            step_id: Unique identifier for this step.
            step: A ``StepType`` instance (Assign, Call, Return, etc.).

        Returns:
            ``self`` for method chaining.
        """
        if not isinstance(step_id, str):
            raise TypeError(f"step_id must be a string, got {type(step_id).__name__}")
        if not isinstance(step, StepType):
            raise TypeError(f"Expected a StepType instance, got {type(step).__name__}")
        self._steps.append((step_id, step))
        return self

    def merge(self, other: "Steps") -> "Steps":
        """Merge all steps from another Steps container and return ``self``.

        Args:
            other: Another ``Steps`` instance whose steps will be appended.

        Returns:
            ``self`` for method chaining.
        """
        if not isinstance(other, Steps):
            raise TypeError(f"Expected a Steps instance, got {type(other).__name__}")
        self._steps.extend(other._steps)
        return self

    def build(self) -> List[Dict[str, Any]]:
        """Serialize all steps to a list of dicts for YAML output.

        Each entry is a single-key dict ``{step_id: <step_body>}``.
        """
        return [step.build(step_id) for step_id, step in self._steps]

    def __len__(self) -> int:
        return len(self._steps)

    # -----------------------------------------------------------------
    # Convenience aliases — delegate to .step(step_id, StepType(...))
    # -----------------------------------------------------------------

    def assign(
        self,
        step_id: str,
        mapping: Optional[Dict[str, Any]] = None,
        /,
        *,
        next: Optional[str] = None,
        **kwargs: Any,
    ) -> "Steps":
        """Add an Assign step.

        Args:
            step_id: Unique identifier for this step.
            mapping: Optional dict of variable assignments (supports
                dot-separated paths).
            next: Jump target step name.
            **kwargs: Simple variable assignments.

        Returns:
            ``self`` for method chaining.

        Example::

            (Steps()
                .assign("init", x=10, y=20)
                .assign("paths", {"a.b.c": 1}))
        """
        return self.step(step_id, _Assign(mapping, next=next, **kwargs))

    def call(
        self,
        step_id: str,
        func: str,
        *,
        args: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
        next: Optional[str] = None,
    ) -> "Steps":
        """Add a Call step.

        Args:
            step_id: Unique identifier for this step.
            func: Function name to call.
            args: Keyword arguments to pass to the function.
            result: Variable name to store the result.
            next: Jump target step name.

        Returns:
            ``self`` for method chaining.

        Example::

            (Steps()
                .call("fetch", "http.get",
                      args={"url": "https://example.com"},
                      result="resp"))
        """
        return self.step(step_id, _Call(func, args=args, result=result, next=next))

    def returns(
        self,
        step_id: str,
        value: Any,
    ) -> "Steps":
        """Add a Return step.

        Args:
            step_id: Unique identifier for this step.
            value: The value to return.

        Returns:
            ``self`` for method chaining.

        Example::

            Steps().returns("done", "ok")
        """
        return self.step(step_id, _Return(value))

    def raises(
        self,
        step_id: str,
        value: Any,
    ) -> "Steps":
        """Add a Raise step.

        Args:
            step_id: Unique identifier for this step.
            value: The error value to raise.

        Returns:
            ``self`` for method chaining.

        Example::

            Steps().raises("fail", {"code": 404, "message": "not found"})
        """
        return self.step(step_id, _Raise(value))

    def switch(
        self,
        step_id: str,
        conditions: List[Condition],
        /,
        *,
        next: Optional[str] = None,
    ) -> "Steps":
        """Add a Switch step.

        Args:
            step_id: Unique identifier for this step.
            conditions: List of ``Condition`` objects.
            next: Default fallthrough target.

        Returns:
            ``self`` for method chaining.

        Example::

            (Steps()
                .switch("check", [
                    Condition(expr("x > 0"), next="positive"),
                    Condition(True, next="negative"),
                ]))
        """
        return self.step(step_id, _Switch(conditions, next=next))

    def loop(
        self,
        step_id: str,
        *,
        value: str,
        items: Any = None,
        range: Any = None,
        index: Optional[str] = None,
        steps: Any,
    ) -> "Steps":
        """Add a For (loop) step.

        Args:
            step_id: Unique identifier for this step.
            value: Loop variable name.
            items: Collection to iterate over (mutually exclusive with
                ``range``).
            range: Range specification ``[start, end, step]``.
            index: Optional index variable name.
            steps: Loop body (``Steps`` container, callable, or list).

        Returns:
            ``self`` for method chaining.

        Example::

            (Steps()
                .loop("iterate",
                      value="item",
                      items=["a", "b", "c"],
                      steps=inner))
        """
        return self.step(
            step_id,
            _For(value=value, items=items, range=range, index=index, steps=steps),
        )

    def parallel(
        self,
        step_id: str,
        *,
        branches: Dict[str, Any],
        shared: Optional[List[str]] = None,
        exception_policy: Optional[str] = None,
        concurrency_limit: Optional[Union[int, str]] = None,
    ) -> "Steps":
        """Add a Parallel step.

        Args:
            step_id: Unique identifier for this step.
            branches: Dict of branch name to ``Steps`` container (or list).
            shared: List of shared variable names.
            exception_policy: Exception handling policy.
            concurrency_limit: Max concurrent branches.

        Returns:
            ``self`` for method chaining.

        Example::

            (Steps()
                .parallel("fan_out",
                          branches={"b1": steps1, "b2": steps2},
                          shared=["result"]))
        """
        return self.step(
            step_id,
            _Parallel(
                branches=branches,
                shared=shared,
                exception_policy=exception_policy,
                concurrency_limit=concurrency_limit,
            ),
        )

    def do_try(
        self,
        step_id: str,
        *,
        steps: Any,
        retry: Optional[Retry] = None,
        error_steps: Optional[Any] = None,
    ) -> "Steps":
        """Add a Try step.

        The try body is auto-detected: a single Call step produces a flat
        ``TryCallBody``; otherwise a ``TryStepsBody`` is used.

        The error variable is always ``e`` (opinionated).

        Args:
            step_id: Unique identifier for this step.
            steps: Try body (``Steps`` container, callable, or list).
            retry: Optional ``Retry`` instance.
            error_steps: Except handler steps.

        Returns:
            ``self`` for method chaining.

        Example::

            (Steps()
                .do_try("safe_call",
                        steps=body_steps,
                        retry=Retry(expr("e.code == 429"),
                                    max_retries=3),
                        error_steps=handler_steps))
        """
        return self.step(
            step_id,
            _Try(steps=steps, retry=retry, error_steps=error_steps),
        )

    def nested(
        self,
        step_id: str,
        *,
        steps: Any,
        next: Optional[str] = None,
    ) -> "Steps":
        """Add a NestedSteps step — group steps under a single step name.

        Args:
            step_id: Unique identifier for this step.
            steps: Nested steps (``Steps`` container or list).
            next: Jump target step name.

        Returns:
            ``self`` for method chaining.

        Example::

            (Steps()
                .nested("group",
                        steps=inner_steps,
                        next="done"))
        """
        return self.step(step_id, _NestedSteps(steps=steps, next=next))

    def _finalize(self) -> Union[SimpleWorkflow, SubworkflowsWorkflow]:
        """Convert this Steps container into a Pydantic workflow model.

        - If this is a plain Steps (no params), produces SimpleWorkflow.
        - If params are set, wraps in SubworkflowsWorkflow with a single
          "main" workflow that has those params.
        """
        if not self._steps:
            raise ValueError("No steps defined")

        step_dicts = self.build()

        if self._params is not None:
            # Has params → SubworkflowsWorkflow
            return SubworkflowsWorkflow(
                workflows={
                    "main": WorkflowDefinition(
                        params=self._params,
                        steps=step_dicts,
                    )
                }
            )
        return SimpleWorkflow(steps=step_dicts)


# =============================================================================
# build() — write workflow definitions to YAML files
# =============================================================================


def build(
    workflows: Dict[str, Union[Dict[str, Steps]]],
    output_dir: Union[str, Path] = ".",
) -> List[Path]:
    """Build workflow definitions and write them to YAML files.

    ``workflows`` is a dict mapping filenames to workflow dicts.

    Each value must be a ``dict[str, Steps]`` mapping workflow names to
    Steps containers.  A ``"main"`` key is required.

    Args:
        workflows: Dict of ``{filename: {name: Steps}}``.
        output_dir: Directory to write files into. Defaults to ``"."``.

    Returns:
        List of ``Path`` objects for every file written.

    Example::

        s = Steps()
        s.step("init", Assign(x=10))
        s.step("done", Return(expr("x")))
        build({"flow.yaml": {"main": s}})

        # Multi-workflow:
        main = Steps()
        main.step("call", Call("helper", result="r"))
        main.step("done", Return(expr("r")))
        helper = Steps(params=["input"])
        helper.step("done", Return("ok"))
        build({"flow.yaml": {"main": main, "helper": helper}})
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

        # Auto-finalize
        workflow_model = _finalize(workflow)

        path = out / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(workflow_model.to_yaml(), encoding="utf-8")
        written.append(path)

    return written


def _finalize(
    value: Any,
) -> Union[SimpleWorkflow, SubworkflowsWorkflow]:
    """Convert a build() value to a finalized workflow model.

    Accepts a ``dict[str, Steps]`` with a required ``"main"`` key.
    """
    if not isinstance(value, dict):
        raise TypeError(f"Expected dict[str, Steps], got {type(value).__name__}")

    if "main" not in value:
        raise ValueError("Workflow dict must contain a 'main' key")

    # Dict of name -> Steps for multi-workflow
    workflows: Dict[str, WorkflowDefinition] = {}
    for name, steps in value.items():
        if not isinstance(steps, Steps):
            raise TypeError(
                f"Multi-workflow dict values must be Steps instances, "
                f"got {type(steps).__name__} for key '{name}'"
            )
        if not steps._steps:
            raise ValueError(f"Workflow '{name}' has no steps")
        workflows[name] = WorkflowDefinition(
            params=steps._params,
            steps=steps.build(),
        )

    # Single 'main' without params → SimpleWorkflow
    if len(workflows) == 1 and "main" in workflows:
        main_wf = workflows["main"]
        if main_wf.params is None:
            return SimpleWorkflow(steps=main_wf.steps)

    return SubworkflowsWorkflow(workflows=workflows)
