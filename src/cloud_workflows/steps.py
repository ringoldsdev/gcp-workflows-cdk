"""Step sub-builder classes for fluent step configuration.

Each class wraps a specific step type with chainable typed methods.
All classes have:
- A constructor for required args
- Chainable methods for optional/additional configuration
- .apply() for type-safe partial merging
- .build() returning the corresponding Pydantic model

Usage:
    from cloud_workflows.steps import Assign, Call, Return_, For, Parallel, Try_

    # Used directly:
    Assign().set("x", 10).set("y", 20).build()  # → AssignStep

    # Or via lambda in StepBuilder.step():
    sb.step("init", "assign", lambda a: a.set("x", 10).set("y", 20))
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Union

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
    SwitchCondition,
    SwitchStep,
    TryCallBody,
    TryStep,
    TryStepsBody,
)

__all__ = [
    "Assign",
    "Call",
    "Return_",
    "Raise_",
    "Switch",
    "For",
    "Parallel",
    "Try_",
    "Steps",
]

# Sentinel for "not yet set" (distinct from None which may be a valid value)
_UNSET = object()


# =============================================================================
# Assign
# =============================================================================


class Assign:
    """Builder for AssignStep.

    Usage:
        Assign().set("x", 10).set("y", 20).build()
        Assign().items([{"x": 10}, {"y": 20}]).build()
    """

    def __init__(self) -> None:
        self._items: List[Dict[str, Any]] = []
        self._next: Optional[str] = None

    def set(self, key: str, value: Any) -> Assign:
        """Add a single assignment {key: value}."""
        self._items.append({key: value})
        return self

    def items(self, items: List[Dict[str, Any]]) -> Assign:
        """Add multiple assignments from a list of single-key dicts."""
        self._items.extend(items)
        return self

    def next(self, target: str) -> Assign:
        """Set the 'next' jump target."""
        self._next = target
        return self

    def apply(self, source: Union[Assign, Callable[[], Optional[Assign]]]) -> Assign:
        """Merge another Assign builder into this one.

        - Items are appended (additive).
        - 'next' is overwritten if the source has it set.

        Args:
            source: An Assign instance, or a callable returning Assign or None.

        Raises:
            TypeError: If source is not an Assign or callable returning Assign/None.
        """
        if callable(source) and not isinstance(source, Assign):
            result = source()
            if result is None:
                return self
            source = result
        if not isinstance(source, Assign):
            raise TypeError(
                f"Assign.apply() requires an Assign instance, got {type(source).__name__}"
            )
        self._items.extend(source._items)
        if source._next is not None:
            self._next = source._next
        return self

    def build(self) -> AssignStep:
        """Build the AssignStep Pydantic model."""
        if not self._items:
            raise ValueError("Assign builder has no items — call .set() or .items()")
        return AssignStep(assign=self._items, next=self._next)


# =============================================================================
# Call
# =============================================================================


class Call:
    """Builder for CallStep.

    Usage:
        Call("sys.log").args(text="hello").build()
        Call("http.get").args(url="...").result("resp").build()
    """

    def __init__(self, function: str = "") -> None:
        self._func: str = function
        self._args: Any = _UNSET
        self._result: Any = _UNSET
        self._next: Optional[str] = None

    def func(self, name: str) -> Call:
        """Set or overwrite the function to call."""
        self._func = name
        return self

    def args(self, **kwargs: Any) -> Call:
        """Set the call arguments."""
        self._args = kwargs
        return self

    def result(self, name: str) -> Call:
        """Set the result variable name."""
        self._result = name
        return self

    def next(self, target: str) -> Call:
        """Set the 'next' jump target."""
        self._next = target
        return self

    def apply(self, source: Union[Call, Callable[[], Optional[Call]]]) -> Call:
        """Merge another Call builder into this one.

        Overwrites only fields that the source has explicitly set.
        """
        if callable(source) and not isinstance(source, Call):
            result = source()
            if result is None:
                return self
            source = result
        if not isinstance(source, Call):
            raise TypeError(
                f"Call.apply() requires a Call instance, got {type(source).__name__}"
            )
        if source._func:
            self._func = source._func
        if source._args is not _UNSET:
            self._args = source._args
        if source._result is not _UNSET:
            self._result = source._result
        if source._next is not None:
            self._next = source._next
        return self

    def build(self) -> CallStep:
        """Build the CallStep Pydantic model."""
        if not self._func:
            raise ValueError(
                "Call builder has no function — call .func() or pass it to constructor"
            )
        return CallStep(
            call=self._func,
            args=self._args if self._args is not _UNSET else None,
            result=self._result if self._result is not _UNSET else None,
            next=self._next,
        )


# =============================================================================
# Return_
# =============================================================================


class Return_:
    """Builder for ReturnStep.

    Usage:
        Return_("ok").build()
        Return_(expr("x + y")).build()
        Return_().value("ok").build()
    """

    def __init__(self, val: Any = _UNSET) -> None:
        self._value: Any = val

    def value(self, v: Any) -> Return_:
        """Set the return value."""
        self._value = v
        return self

    def apply(self, source: Union[Return_, Callable[[], Optional[Return_]]]) -> Return_:
        """Merge another Return_ builder — overwrites value."""
        if callable(source) and not isinstance(source, Return_):
            result = source()
            if result is None:
                return self
            source = result
        if not isinstance(source, Return_):
            raise TypeError(
                f"Return_.apply() requires a Return_ instance, got {type(source).__name__}"
            )
        if source._value is not _UNSET:
            self._value = source._value
        return self

    def build(self) -> ReturnStep:
        """Build the ReturnStep Pydantic model."""
        if self._value is _UNSET:
            raise ValueError(
                "Return_ builder has no value — call .value() or pass it to constructor"
            )
        return ReturnStep(return_=self._value)


# =============================================================================
# Raise_
# =============================================================================


class Raise_:
    """Builder for RaiseStep.

    Usage:
        Raise_({"code": 404}).build()
        Raise_(expr("e")).build()
        Raise_().value("error").build()
    """

    def __init__(self, val: Any = _UNSET) -> None:
        self._value: Any = val

    def value(self, v: Any) -> Raise_:
        """Set the raise value."""
        self._value = v
        return self

    def apply(self, source: Union[Raise_, Callable[[], Optional[Raise_]]]) -> Raise_:
        """Merge another Raise_ builder — overwrites value."""
        if callable(source) and not isinstance(source, Raise_):
            result = source()
            if result is None:
                return self
            source = result
        if not isinstance(source, Raise_):
            raise TypeError(
                f"Raise_.apply() requires a Raise_ instance, got {type(source).__name__}"
            )
        if source._value is not _UNSET:
            self._value = source._value
        return self

    def build(self) -> RaiseStep:
        """Build the RaiseStep Pydantic model."""
        if self._value is _UNSET:
            raise ValueError(
                "Raise_ builder has no value — call .value() or pass it to constructor"
            )
        return RaiseStep(raise_=self._value)


# =============================================================================
# Switch
# =============================================================================


class Switch:
    """Builder for SwitchStep.

    Usage:
        Switch()
            .condition(expr("x > 0"), next="positive")
            .condition(True, next="negative")
            .build()
    """

    def __init__(self) -> None:
        self._conditions: List[Dict[str, Any]] = []
        self._next: Optional[str] = None

    def condition(
        self,
        cond: Any,
        *,
        next: Optional[str] = None,
        steps: Optional[Any] = None,
        assign: Optional[List[Dict[str, Any]]] = None,
        return_: Any = _UNSET,
        raise_: Any = _UNSET,
    ) -> Switch:
        """Add a switch condition."""
        entry: Dict[str, Any] = {"condition": cond}
        if next is not None:
            entry["next"] = next
        if steps is not None:
            # steps can be a StepBuilder — resolve at build time
            entry["steps"] = steps
        if assign is not None:
            entry["assign"] = assign
        if return_ is not _UNSET:
            entry["return"] = return_
        if raise_ is not _UNSET:
            entry["raise"] = raise_
        self._conditions.append(entry)
        return self

    def next(self, target: str) -> Switch:
        """Set the 'next' fallthrough target."""
        self._next = target
        return self

    def apply(self, source: Union[Switch, Callable[[], Optional[Switch]]]) -> Switch:
        """Merge another Switch builder.

        - Conditions are appended (additive).
        - 'next' is overwritten if the source has it set.
        """
        if callable(source) and not isinstance(source, Switch):
            result = source()
            if result is None:
                return self
            source = result
        if not isinstance(source, Switch):
            raise TypeError(
                f"Switch.apply() requires a Switch instance, got {type(source).__name__}"
            )
        self._conditions.extend(source._conditions)
        if source._next is not None:
            self._next = source._next
        return self

    def build(self) -> SwitchStep:
        """Build the SwitchStep Pydantic model."""
        if not self._conditions:
            raise ValueError("Switch builder has no conditions — call .condition()")
        conditions = []
        for entry in self._conditions:
            # Resolve StepBuilder in steps if present
            raw_steps = entry.get("steps")
            if raw_steps is not None and hasattr(raw_steps, "build"):
                from .builder import StepBuilder

                if isinstance(raw_steps, StepBuilder):
                    entry = dict(entry)
                    entry["steps"] = [
                        {s.name: s.body.model_dump(by_alias=True, exclude_none=True)}
                        for s in raw_steps.build()
                    ]
            conditions.append(SwitchCondition(**entry))
        return SwitchStep(switch=conditions, next=self._next)


# =============================================================================
# For
# =============================================================================


class For:
    """Builder for ForStep.

    Usage:
        For("item").in_(["a", "b"]).steps(step_builder).build()
        For("i").range_([0, 10]).steps(step_builder).build()
    """

    def __init__(self, value: str = "") -> None:
        self._value: str = value
        self._in: Any = _UNSET
        self._range: Any = _UNSET
        self._index: Optional[str] = None
        self._steps: Any = None  # StepBuilder or None

    def value(self, name: str) -> For:
        """Set the loop variable name."""
        self._value = name
        return self

    def in_(self, items: Any) -> For:
        """Set the collection to iterate over."""
        self._in = items
        return self

    def range_(self, r: Any) -> For:
        """Set the range to iterate over."""
        self._range = r
        return self

    def index(self, name: str) -> For:
        """Set the index variable name."""
        self._index = name
        return self

    def steps(self, sb: Any) -> For:
        """Set the loop body steps (a StepBuilder)."""
        self._steps = sb
        return self

    def apply(self, source: Union[For, Callable[[], Optional[For]]]) -> For:
        """Merge another For builder — overwrites set fields, replaces steps."""
        if callable(source) and not isinstance(source, For):
            result = source()
            if result is None:
                return self
            source = result
        if not isinstance(source, For):
            raise TypeError(
                f"For.apply() requires a For instance, got {type(source).__name__}"
            )
        if source._value:
            self._value = source._value
        if source._in is not _UNSET:
            self._in = source._in
        if source._range is not _UNSET:
            self._range = source._range
        if source._index is not None:
            self._index = source._index
        if source._steps is not None:
            self._steps = source._steps
        return self

    def build(self) -> ForStep:
        """Build the ForStep Pydantic model."""
        if not self._value:
            raise ValueError(
                "For builder has no value variable — pass it to constructor or call .value()"
            )
        if self._steps is None:
            raise ValueError("For builder has no steps — call .steps()")

        # Resolve StepBuilder to list of step dicts
        from .builder import StepBuilder

        if isinstance(self._steps, StepBuilder):
            step_dicts = [
                {s.name: s.body.model_dump(by_alias=True, exclude_none=True)}
                for s in self._steps.build()
            ]
        else:
            step_dicts = self._steps

        return ForStep(
            for_=ForBody(
                value=self._value,
                index=self._index,
                in_=self._in if self._in is not _UNSET else None,
                range=self._range if self._range is not _UNSET else None,
                steps=step_dicts,
            )
        )


# =============================================================================
# Parallel
# =============================================================================


class Parallel:
    """Builder for ParallelStep.

    Usage:
        Parallel()
            .branch("b1", step_builder_1)
            .branch("b2", step_builder_2)
            .build()
    """

    def __init__(self) -> None:
        self._branches: List[tuple[str, Any]] = []  # (name, StepBuilder)
        self._shared: Optional[List[str]] = None
        self._exception_policy: Optional[str] = None
        self._concurrency_limit: Optional[Union[int, str]] = None

    def branch(self, name: str, steps: Any) -> Parallel:
        """Add a parallel branch."""
        self._branches.append((name, steps))
        return self

    def shared(self, vars: List[str]) -> Parallel:
        """Set shared variable names."""
        self._shared = vars
        return self

    def exception_policy(self, policy: str) -> Parallel:
        """Set exception policy (e.g. 'continueAll')."""
        self._exception_policy = policy
        return self

    def concurrency_limit(self, limit: Union[int, str]) -> Parallel:
        """Set concurrency limit."""
        self._concurrency_limit = limit
        return self

    def apply(
        self, source: Union[Parallel, Callable[[], Optional[Parallel]]]
    ) -> Parallel:
        """Merge another Parallel builder.

        - Branches are appended (additive).
        - shared/exception_policy/concurrency_limit are overwritten if set.
        """
        if callable(source) and not isinstance(source, Parallel):
            result = source()
            if result is None:
                return self
            source = result
        if not isinstance(source, Parallel):
            raise TypeError(
                f"Parallel.apply() requires a Parallel instance, got {type(source).__name__}"
            )
        self._branches.extend(source._branches)
        if source._shared is not None:
            self._shared = source._shared
        if source._exception_policy is not None:
            self._exception_policy = source._exception_policy
        if source._concurrency_limit is not None:
            self._concurrency_limit = source._concurrency_limit
        return self

    def build(self) -> ParallelStep:
        """Build the ParallelStep Pydantic model."""
        if not self._branches:
            raise ValueError("Parallel builder has no branches — call .branch()")

        from .builder import StepBuilder

        branches = []
        for name, steps in self._branches:
            if isinstance(steps, StepBuilder):
                step_dicts = [
                    {s.name: s.body.model_dump(by_alias=True, exclude_none=True)}
                    for s in steps.build()
                ]
            else:
                step_dicts = steps
            branches.append(Branch(name=name, steps=step_dicts))

        return ParallelStep(
            parallel=ParallelBody(
                branches=branches,
                shared=self._shared,
                exception_policy=self._exception_policy,
                concurrency_limit=self._concurrency_limit,
            )
        )


# =============================================================================
# Try_
# =============================================================================


class Try_:
    """Builder for TryStep.

    Usage:
        Try_(body_step_builder)
            .retry(predicate=expr("e.code == 429"), max_retries=3, backoff={...})
            .except_(as_="e", steps=except_step_builder)
            .build()
    """

    def __init__(self, body: Any = None) -> None:
        self._body: Any = body  # StepBuilder
        self._retry: Any = _UNSET
        self._except_as: Optional[str] = None
        self._except_steps: Any = None  # StepBuilder

    def body(self, sb: Any) -> Try_:
        """Set the try body (a StepBuilder)."""
        self._body = sb
        return self

    def retry(
        self,
        *,
        predicate: str,
        max_retries: int,
        backoff: Dict[str, Any],
    ) -> Try_:
        """Set retry configuration."""
        self._retry = {
            "predicate": predicate,
            "max_retries": max_retries,
            "backoff": backoff,
        }
        return self

    def except_(self, *, as_: str, steps: Any) -> Try_:
        """Set except handler."""
        self._except_as = as_
        self._except_steps = steps
        return self

    def apply(self, source: Union[Try_, Callable[[], Optional[Try_]]]) -> Try_:
        """Merge another Try_ builder — overwrites body/retry/except."""
        if callable(source) and not isinstance(source, Try_):
            result = source()
            if result is None:
                return self
            source = result
        if not isinstance(source, Try_):
            raise TypeError(
                f"Try_.apply() requires a Try_ instance, got {type(source).__name__}"
            )
        if source._body is not None:
            self._body = source._body
        if source._retry is not _UNSET:
            self._retry = source._retry
        if source._except_as is not None:
            self._except_as = source._except_as
        if source._except_steps is not None:
            self._except_steps = source._except_steps
        return self

    def build(self) -> TryStep:
        """Build the TryStep Pydantic model."""
        if self._body is None:
            raise ValueError(
                "Try_ builder has no body — call .body() or pass it to constructor"
            )

        from .builder import StepBuilder

        # Resolve body: StepBuilder with a single call step → TryCallBody
        # StepBuilder with multiple steps → TryStepsBody
        if isinstance(self._body, StepBuilder):
            body_steps = self._body.build()
            if len(body_steps) == 1:
                body_model = body_steps[0].body
                if isinstance(body_model, CallStep):
                    try_body = TryCallBody(
                        call=body_model.call,
                        args=body_model.args,
                        result=body_model.result,
                    )
                else:
                    step_dicts = [
                        {s.name: s.body.model_dump(by_alias=True, exclude_none=True)}
                        for s in body_steps
                    ]
                    try_body = TryStepsBody(steps=step_dicts)
            else:
                step_dicts = [
                    {s.name: s.body.model_dump(by_alias=True, exclude_none=True)}
                    for s in body_steps
                ]
                try_body = TryStepsBody(steps=step_dicts)
        else:
            try_body = self._body

        # Resolve retry
        retry = None
        if self._retry is not _UNSET:
            if isinstance(self._retry, dict):
                backoff_data = self._retry["backoff"]
                if isinstance(backoff_data, dict):
                    backoff = BackoffConfig(**backoff_data)
                else:
                    backoff = backoff_data
                retry = RetryConfig(
                    predicate=self._retry["predicate"],
                    max_retries=self._retry["max_retries"],
                    backoff=backoff,
                )
            elif isinstance(self._retry, str):
                retry = self._retry
            else:
                retry = self._retry

        # Resolve except
        except_body = None
        if self._except_as is not None and self._except_steps is not None:
            if isinstance(self._except_steps, StepBuilder):
                except_step_dicts = [
                    {s.name: s.body.model_dump(by_alias=True, exclude_none=True)}
                    for s in self._except_steps.build()
                ]
            else:
                except_step_dicts = self._except_steps
            except_body = ExceptBody(as_=self._except_as, steps=except_step_dicts)

        return TryStep(
            try_=try_body,
            retry=retry,
            except_=except_body,
        )


# =============================================================================
# Steps (nested steps)
# =============================================================================


class Steps:
    """Builder for NestedStepsStep.

    Usage:
        Steps(inner_step_builder).next("done").build()
    """

    def __init__(self, body: Any = None) -> None:
        self._body: Any = body  # StepBuilder
        self._next: Optional[str] = None

    def body(self, sb: Any) -> Steps:
        """Set the nested steps body (a StepBuilder)."""
        self._body = sb
        return self

    def next(self, target: str) -> Steps:
        """Set the 'next' jump target."""
        self._next = target
        return self

    def apply(self, source: Union[Steps, Callable[[], Optional[Steps]]]) -> Steps:
        """Merge another Steps builder — replaces body, overwrites next."""
        if callable(source) and not isinstance(source, Steps):
            result = source()
            if result is None:
                return self
            source = result
        if not isinstance(source, Steps):
            raise TypeError(
                f"Steps.apply() requires a Steps instance, got {type(source).__name__}"
            )
        if source._body is not None:
            self._body = source._body
        if source._next is not None:
            self._next = source._next
        return self

    def build(self) -> NestedStepsStep:
        """Build the NestedStepsStep Pydantic model."""
        if self._body is None:
            raise ValueError(
                "Steps builder has no body — call .body() or pass it to constructor"
            )

        from .builder import StepBuilder

        if isinstance(self._body, StepBuilder):
            step_dicts = [
                {s.name: s.body.model_dump(by_alias=True, exclude_none=True)}
                for s in self._body.build()
            ]
        else:
            step_dicts = self._body

        return NestedStepsStep(steps=step_dicts, next=self._next)
