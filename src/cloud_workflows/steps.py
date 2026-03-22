"""Step classes for constructing Cloud Workflows programmatically.

Each step class represents a GCP Workflows step type. Instances are
immutable descriptions of a step's configuration. They are added to a
``Steps`` container via its ``__call__`` method::

    s = Steps()
    s("init", Assign(x=10, y=20))
    s("log", Call("sys.log", args={"text": expr("x")}))
    s("done", Return(expr("x + y")))

Step classes:
    Assign      — variable assignment
    Call        — function/subworkflow call
    Return      — return a value
    Raise       — raise an error
    Switch      — conditional branching
    For         — for-loop iteration
    Parallel    — parallel branches
    Try         — try/retry/except
    NestedSteps — nested step group

Each class has a ``build(step_id)`` method that returns a single-entry dict
``{step_id: <step_body>}`` ready for YAML serialization.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from jsonpath_ng import parse as jp_parse

from .models import (
    AssignStep,
    BackoffConfig,
    Branch,
    CallStep,
    ExceptBody,
    ForBody,
    ForStep,
    NestedStepsStep,
    ParallelBody,
    ParallelStep,
    RaiseStep,
    RetryConfig,
    ReturnStep,
    Step,
    SwitchCondition,
    SwitchStep,
    TryCallBody,
    TryStep,
    TryStepsBody,
)

__all__ = [
    "StepType",
    "Assign",
    "Call",
    "Return",
    "Raise",
    "Switch",
    "Condition",
    "For",
    "Parallel",
    "Try",
    "NestedSteps",
]

# ---------------------------------------------------------------------------
# Sentinel for "not provided" where None may be valid
# ---------------------------------------------------------------------------
_UNSET = object()


# ============================================================================
# StepType base
# ============================================================================


class StepType:
    """Base class for all step types.

    Subclasses must implement ``build(step_id)`` which returns a dict
    ``{step_id: <step_body_dict>}`` suitable for YAML serialization.
    """

    def build(self, step_id: str) -> Dict[str, Any]:
        """Return ``{step_id: <body>}`` for YAML output."""
        raise NotImplementedError


# ============================================================================
# Helper: resolve a Steps container to a list of dicts
# ============================================================================


def _resolve_steps(steps: Any) -> List[Dict[str, Any]]:
    """Convert a Steps container (or raw list) to a list of step dicts.

    Accepts:
    - A ``Steps`` instance (from builder.py) → calls ``.build()``
    - A raw ``list`` of dicts → returned as-is
    """
    # Import here to avoid circular imports
    from .builder import Steps

    if isinstance(steps, Steps):
        return steps.build()
    if isinstance(steps, list):
        return steps
    raise TypeError(
        f"Expected Steps instance or list of dicts, got {type(steps).__name__}"
    )


# ============================================================================
# Assign
# ============================================================================


class Assign(StepType):
    """Assign step — set one or more variables.

    Usage::

        Assign(x=10, y=20)
        Assign({"a.b.c": 1}, x=10)    # dict for dotted paths
        Assign(x=10, next="done")      # with jump target

    Args:
        mapping: Optional dict of variable assignments.  Keys may use
            dot-separated paths (e.g. ``"a.b.c"``) which are expanded
            into nested dicts.
        next: Jump target step name.
        **kwargs: Simple variable assignments.
    """

    def __init__(
        self,
        mapping: Optional[Dict[str, Any]] = None,
        /,
        *,
        next: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        items: List[Dict[str, Any]] = []
        if mapping:
            for key, value in mapping.items():
                items.append(_expand_dotpath(key, value))
        for key, value in kwargs.items():
            items.append(_expand_dotpath(key, value))
        if not items:
            raise ValueError("Assign requires at least one assignment")
        self._items = items
        self._next = next

    def build(self, step_id: str) -> Dict[str, Any]:
        model = AssignStep(assign=self._items, next=self._next)
        body = model.model_dump(by_alias=True, exclude_none=True)
        return {step_id: body}


def _expand_dotpath(key: str, value: Any) -> Dict[str, Any]:
    """Expand a dot-separated key into nested dicts.

    ``_expand_dotpath("a.b.c", 1)`` → ``{"a": {"b": {"c": 1}}}``
    """
    if "." in key:
        result: Dict[str, Any] = {}
        jp_parse(key).update_or_create(result, value)
        return result
    return {key: value}


# ============================================================================
# Call
# ============================================================================


class Call(StepType):
    """Call step — invoke a function or subworkflow.

    Usage::

        Call("sys.log", args={"text": "hello"})
        Call("http.get", args={"url": url}, result="resp")
        Call("http.get", args={"url": url}, result="resp", next="done")

    Args:
        func: Function name to call.
        args: Keyword arguments to pass.
        result: Variable name to store the result.
        next: Jump target step name.
    """

    def __init__(
        self,
        func: str,
        *,
        args: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
        next: Optional[str] = None,
    ) -> None:
        if not func:
            raise ValueError("Call requires a function name")
        self._func = func
        self._args = args
        self._result = result
        self._next = next

    def build(self, step_id: str) -> Dict[str, Any]:
        model = CallStep(
            call=self._func,
            args=self._args,
            result=self._result,
            next=self._next,
        )
        body = model.model_dump(by_alias=True, exclude_none=True)
        return {step_id: body}


# ============================================================================
# Return
# ============================================================================


class Return(StepType):
    """Return step — return a value from the workflow.

    Usage::

        Return("ok")
        Return(expr("x + y"))
        Return(None)               # explicit None return

    Args:
        value: The value to return.
    """

    def __init__(self, value: Any = _UNSET) -> None:
        if value is _UNSET:
            raise ValueError("Return requires a value")
        self._value = value

    def build(self, step_id: str) -> Dict[str, Any]:
        model = ReturnStep(return_=self._value)
        body = model.model_dump(by_alias=True, exclude_none=True)
        return {step_id: body}


# ============================================================================
# Raise
# ============================================================================


class Raise(StepType):
    """Raise step — raise an error.

    Usage::

        Raise("something went wrong")
        Raise({"code": 404, "message": "not found"})
        Raise(expr("e"))

    Args:
        value: The error value to raise.
    """

    def __init__(self, value: Any = _UNSET) -> None:
        if value is _UNSET:
            raise ValueError("Raise requires a value")
        self._value = value

    def build(self, step_id: str) -> Dict[str, Any]:
        model = RaiseStep(raise_=self._value)
        body = model.model_dump(by_alias=True, exclude_none=True)
        return {step_id: body}


# ============================================================================
# Condition (for Switch)
# ============================================================================


class Condition:
    """A single condition entry for a Switch step.

    Usage::

        Condition(expr("x > 0"), next="positive")
        Condition(expr("x < 0"), return_="negative")
        Condition(True, raise_={"code": 400})
        Condition(expr("x > 0"), steps=inner_steps)
        Condition(expr("x > 0"), assign=[{"y": 1}])

    Args:
        condition: The condition expression.
        next: Jump target step name.
        steps: Inline steps to execute if condition is true.
        assign: Inline assignments if condition is true.
        return_: Return value if condition is true.
        raise_: Raise value if condition is true.
    """

    def __init__(
        self,
        condition: Any,
        *,
        next: Optional[str] = None,
        steps: Any = None,
        assign: Optional[List[Dict[str, Any]]] = None,
        return_: Any = _UNSET,
        raise_: Any = _UNSET,
    ) -> None:
        self.condition = condition
        self.next = next
        self.steps = steps
        self.assign = assign
        self.return_ = return_
        self.raise_ = raise_

    def _to_model(self) -> SwitchCondition:
        """Convert to a SwitchCondition Pydantic model."""
        kwargs: Dict[str, Any] = {"condition": self.condition}
        if self.next is not None:
            kwargs["next"] = self.next
        if self.steps is not None:
            kwargs["steps"] = _resolve_steps(self.steps)
        if self.assign is not None:
            kwargs["assign"] = self.assign
        if self.return_ is not _UNSET:
            # SwitchCondition uses alias "return" for field return_
            kwargs["return"] = self.return_
        if self.raise_ is not _UNSET:
            # SwitchCondition uses alias "raise" for field raise_
            kwargs["raise"] = self.raise_
        return SwitchCondition(**kwargs)


# ============================================================================
# Switch
# ============================================================================


class Switch(StepType):
    """Switch step — conditional branching.

    Usage::

        Switch(
            conditions=[
                Condition(expr("x > 0"), next="positive"),
                Condition(True, next="negative"),
            ],
            next="fallback",
        )

    Args:
        conditions: List of Condition objects.
        next: Default fallthrough target.
    """

    def __init__(
        self,
        conditions: List[Condition],
        *,
        next: Optional[str] = None,
    ) -> None:
        if not conditions:
            raise ValueError("Switch requires at least one condition")
        self._conditions = conditions
        self._next = next

    def build(self, step_id: str) -> Dict[str, Any]:
        model = SwitchStep(
            switch=[c._to_model() for c in self._conditions],
            next=self._next,
        )
        body = model.model_dump(by_alias=True, exclude_none=True)
        return {step_id: body}


# ============================================================================
# For
# ============================================================================


class For(StepType):
    """For step — iterate over a collection or range.

    Usage::

        For(value="item", in_=["a", "b", "c"], steps=inner)
        For(value="item", range=[1, 10, 2], steps=inner)
        For(value="item", in_=items, index="idx", steps=inner)

    Args:
        value: Loop variable name.
        in_: Collection to iterate over (mutually exclusive with range).
        range: Range specification [start, end, step].
        index: Optional index variable name.
        steps: Loop body (Steps container or list of dicts).
    """

    def __init__(
        self,
        *,
        value: str,
        in_: Any = None,
        range: Any = None,
        index: Optional[str] = None,
        steps: Any,
    ) -> None:
        if not value:
            raise ValueError("For requires a value variable name")
        if in_ is None and range is None:
            raise ValueError("For requires either in_ or range")
        self._value = value
        self._in = in_
        self._range = range
        self._index = index
        self._steps = steps

    def build(self, step_id: str) -> Dict[str, Any]:
        step_dicts = _resolve_steps(self._steps)
        model = ForStep(
            for_=ForBody(
                value=self._value,
                index=self._index,
                in_=self._in,
                range=self._range,
                steps=step_dicts,
            )
        )
        body = model.model_dump(by_alias=True, exclude_none=True)
        return {step_id: body}


# ============================================================================
# Parallel
# ============================================================================


class Parallel(StepType):
    """Parallel step — execute branches concurrently.

    Usage::

        Parallel(branches={"b1": steps1, "b2": steps2})
        Parallel(
            branches={"b1": steps1, "b2": steps2},
            shared=["result"],
            exception_policy="continueAll",
        )

    Args:
        branches: Dict of branch name → Steps container (or list of dicts).
        shared: List of shared variable names.
        exception_policy: Exception handling policy.
        concurrency_limit: Max concurrent branches.
    """

    def __init__(
        self,
        *,
        branches: Dict[str, Any],
        shared: Optional[List[str]] = None,
        exception_policy: Optional[str] = None,
        concurrency_limit: Optional[Union[int, str]] = None,
    ) -> None:
        if not branches:
            raise ValueError("Parallel requires at least one branch")
        self._branches = branches
        self._shared = shared
        self._exception_policy = exception_policy
        self._concurrency_limit = concurrency_limit

    def build(self, step_id: str) -> Dict[str, Any]:
        branch_models = []
        for name, steps in self._branches.items():
            step_dicts = _resolve_steps(steps)
            branch_models.append(Branch(name=name, steps=step_dicts))

        model = ParallelStep(
            parallel=ParallelBody(
                branches=branch_models,
                shared=self._shared,
                exception_policy=self._exception_policy,
                concurrency_limit=self._concurrency_limit,
            )
        )
        body = model.model_dump(by_alias=True, exclude_none=True)
        return {step_id: body}


# ============================================================================
# Try
# ============================================================================


class Try(StepType):
    """Try step — try/retry/except error handling.

    The try body is auto-detected:
    - If ``steps`` contains a single Call step, it produces a ``TryCallBody``
      (flat call fields in the try block).
    - Otherwise it produces a ``TryStepsBody`` (nested steps list).

    Usage::

        Try(
            steps=body_steps,
            retry={"predicate": expr("e.code == 429"), "max_retries": 3,
                    "backoff": {"initial_delay": 1, "max_delay": 30, "multiplier": 2}},
            except_={"as": "e", "steps": except_steps},
        )

        # Retry with a string predicate:
        Try(steps=body_steps, retry="http.default_retry")

    Args:
        steps: Try body (Steps container or list of dicts).
        retry: Retry configuration — dict with predicate/max_retries/backoff,
            a RetryConfig model, or a string predicate name.
        except_: Except handler — dict with "as" and "steps" keys,
            or an ExceptBody model.
    """

    def __init__(
        self,
        *,
        steps: Any,
        retry: Optional[Union[Dict[str, Any], RetryConfig, str]] = None,
        except_: Optional[Union[Dict[str, Any], ExceptBody]] = None,
    ) -> None:
        self._steps = steps
        self._retry_raw = retry
        self._except_raw = except_

    def build(self, step_id: str) -> Dict[str, Any]:
        step_dicts = _resolve_steps(self._steps)

        # Auto-detect try body type
        try_body = self._build_try_body(step_dicts)

        # Resolve retry
        retry = self._build_retry()

        # Resolve except
        except_body = self._build_except()

        model = TryStep(try_=try_body, retry=retry, except_=except_body)
        body = model.model_dump(by_alias=True, exclude_none=True)
        return {step_id: body}

    def _build_try_body(self, step_dicts: List[Dict[str, Any]]) -> Any:
        """Auto-detect whether to use TryCallBody or TryStepsBody."""
        if len(step_dicts) == 1:
            single = step_dicts[0]
            # Single step — check if it's a call
            step_name = list(single.keys())[0]
            step_body = single[step_name]
            if isinstance(step_body, dict) and "call" in step_body:
                return TryCallBody(
                    call=step_body["call"],
                    args=step_body.get("args"),
                    result=step_body.get("result"),
                )
        return TryStepsBody(steps=step_dicts)

    def _build_retry(self) -> Any:
        """Resolve retry configuration."""
        if self._retry_raw is None:
            return None
        if isinstance(self._retry_raw, (RetryConfig, str)):
            return self._retry_raw
        if isinstance(self._retry_raw, dict):
            backoff_data = self._retry_raw.get("backoff")
            backoff = (
                BackoffConfig(**backoff_data)
                if isinstance(backoff_data, dict)
                else backoff_data
            )
            return RetryConfig(
                predicate=self._retry_raw["predicate"],
                max_retries=self._retry_raw["max_retries"],
                backoff=backoff,
            )
        return self._retry_raw

    def _build_except(self) -> Optional[ExceptBody]:
        """Resolve except handler."""
        if self._except_raw is None:
            return None
        if isinstance(self._except_raw, ExceptBody):
            return self._except_raw
        if isinstance(self._except_raw, dict):
            as_var = self._except_raw.get("as") or self._except_raw.get("as_")
            steps_raw = self._except_raw["steps"]
            step_dicts = _resolve_steps(steps_raw)
            return ExceptBody(as_=as_var, steps=step_dicts)
        raise TypeError(
            f"except_ must be a dict or ExceptBody, got {type(self._except_raw).__name__}"
        )


# ============================================================================
# NestedSteps
# ============================================================================


class NestedSteps(StepType):
    """Nested steps — group steps under a single step name.

    Usage::

        NestedSteps(steps=inner_steps, next="done")

    Args:
        steps: Nested steps (Steps container or list of dicts).
        next: Jump target step name.
    """

    def __init__(
        self,
        *,
        steps: Any,
        next: Optional[str] = None,
    ) -> None:
        self._steps = steps
        self._next = next

    def build(self, step_id: str) -> Dict[str, Any]:
        step_dicts = _resolve_steps(self._steps)
        model = NestedStepsStep(steps=step_dicts, next=self._next)
        body = model.model_dump(by_alias=True, exclude_none=True)
        return {step_id: body}
