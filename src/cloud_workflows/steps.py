"""Step sub-builder classes for fluent step configuration.

All step types extend ``StepBase``, which provides:
- A dict-based ``_state`` store
- ``set(path, value)`` using *jsonpath-ng* for nested-key creation
- ``apply(source)`` using *deepmerge* for deep-merging another builder's state

Subclasses add typed convenience methods (e.g. ``Call.func()``, ``Loop.in_()``)
and a ``build()`` method that emits the matching Pydantic model.

Aliases are provided for classes that would otherwise require trailing
underscores: ``Returns``/``DoReturn`` for ``Return_``,
``Raises``/``DoRaise`` for ``Raise_``, ``DoTry`` for ``Try_``,
and ``Loop`` for ``For``.

Usage:
    from cloud_workflows.steps import Assign, Call, Returns, Loop, Parallel, DoTry

    # Used directly:
    Assign().set("x", 10).set("y", 20).build()  # → AssignStep

    # Or via lambda in StepBuilder:
    sb.assign("init", lambda a: a.set("x", 10).set("y", 20))
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union

from deepmerge import Merger
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
    SwitchCondition,
    SwitchStep,
    TryCallBody,
    TryStep,
    TryStepsBody,
)

__all__ = [
    "StepBase",
    "Assign",
    "Call",
    "Return_",
    "Returns",
    "DoReturn",
    "Raise_",
    "Raises",
    "DoRaise",
    "Switch",
    "For",
    "Loop",
    "Parallel",
    "Try_",
    "DoTry",
    "Steps",
]

# ---------------------------------------------------------------------------
# Sentinel for "not provided" in Switch.condition() where None may be valid
# ---------------------------------------------------------------------------
_UNSET = object()

# ---------------------------------------------------------------------------
# Merger configuration
# ---------------------------------------------------------------------------
# Dicts: recursive merge.  Lists: append (additive).  Scalars: override.
_merger = Merger(
    [(dict, ["merge"]), (list, ["append"])],
    ["override"],
    ["override"],
)

_T = TypeVar("_T")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_source(
    source: Any, expected_type: Type[_T], type_name: str
) -> Optional[_T]:
    """Resolve an apply() source to the expected type.

    Handles callables that return the expected type or None.
    """
    if callable(source) and not isinstance(source, expected_type):
        result = source()
        if result is None:
            return None
        source = result
    if not isinstance(source, expected_type):
        raise TypeError(
            f"{type_name}.apply() requires a {type_name} instance, "
            f"got {type(source).__name__}"
        )
    return source


def _resolve_step_builder(sb: Any) -> List[Dict[str, Any]]:
    """Convert a StepBuilder, callable, or raw list into a list of step dicts.

    If ``sb`` is a StepBuilder, calls ``.build()`` and serializes each step
    via ``model_dump(by_alias=True, exclude_none=True)``.  If ``sb`` is a
    callable (lambda), creates a new StepBuilder, passes it to the callable,
    and resolves the result.  Otherwise returns ``sb`` unchanged (assumed to
    already be a list of dicts).
    """
    from .builder import StepBuilder

    if callable(sb) and not isinstance(sb, StepBuilder):
        builder = StepBuilder()
        sb(builder)
        sb = builder
    if isinstance(sb, StepBuilder):
        return [
            {s.name: s.body.model_dump(by_alias=True, exclude_none=True)}
            for s in sb.build()
        ]
    return sb


# ============================================================================
# StepBase
# ============================================================================


class StepBase:
    """Base class for all step sub-builders.

    Stores internal state in a plain ``dict`` (``self._state``).

    * **set(path, value)** — set a value at an arbitrary path.  Dot-separated
      paths (e.g. ``"a.b.c"``) create nested dicts automatically via
      *jsonpath-ng* ``update_or_create``.
    * **get(key, default)** — read a top-level key from state.
    * **has(key)** — check if a top-level key is present.
    * **apply(source)** — deep-merge another builder of the **same type**
      into this one using *deepmerge*.
    """

    def __init__(self, **initial: Any) -> None:
        self._state: Dict[str, Any] = dict(initial)

    # -- state access helpers ------------------------------------------------

    def set(self, path: str, value: Any) -> StepBase:
        """Set a value at *path*, creating nested structure as needed.

        ``set("a.b.c", 1)`` results in ``{"a": {"b": {"c": 1}}}`` being
        merged into ``_state``.
        """
        if "." in path:
            # Build a temporary nested dict via jsonpath-ng, then deep-merge
            # it into _state so existing keys are preserved.
            tmp: Dict[str, Any] = {}
            jp_parse(path).update_or_create(tmp, value)
            _merger.merge(self._state, tmp)
        else:
            self._state[path] = value
        return self

    def get(self, key: str, default: Any = None) -> Any:
        """Read a top-level key from the internal state."""
        return self._state.get(key, default)

    def has(self, key: str) -> bool:
        """Return ``True`` if *key* is present in the state dict."""
        return key in self._state

    # -- deep-merge ----------------------------------------------------------

    def apply(self, source: Any) -> StepBase:
        """Deep-merge *source*'s state into this builder.

        *source* may be:
        - An instance of the **same class** — its ``_state`` is deep-merged.
        - A callable returning such an instance (or ``None`` to skip).

        Raises ``TypeError`` if the resolved source is the wrong type.
        """
        resolved = _resolve_source(source, type(self), type(self).__name__)
        if resolved is None:
            return self
        _merger.merge(self._state, deepcopy(resolved._state))
        return self

    def build(self) -> Any:
        """Build the corresponding Pydantic model.

        Subclasses must override this method.
        """
        raise NotImplementedError


# ============================================================================
# Assign
# ============================================================================


class Assign(StepBase):
    """Builder for AssignStep.

    Internal state keys:
        items : List[Dict[str, Any]]  — accumulated assignments
        next  : Optional[str]         — jump target

    Usage::

        Assign().set("x", 10).set("y", 20).build()
        Assign().items([{"x": 10}, {"y": 20}]).build()
    """

    def __init__(self) -> None:
        super().__init__(items=[], next=None)

    # -- override set() to append to items instead of setting a path ---------

    def set(self, key: str, value: Any) -> Assign:  # type: ignore[override]
        """Add a single assignment.

        Dot-separated keys are unnested into nested dicts:
        ``set("a.b.c", 1)`` appends ``{"a": {"b": {"c": 1}}}``.
        """
        if "." in key:
            nested: Dict[str, Any] = {}
            jp_parse(key).update_or_create(nested, value)
            self._state["items"].append(nested)
        else:
            self._state["items"].append({key: value})
        return self

    def items(self, items: List[Dict[str, Any]]) -> Assign:
        """Add multiple assignments from a list of single-key dicts."""
        self._state["items"].extend(items)
        return self

    def next(self, target: str) -> Assign:
        """Set the 'next' jump target."""
        self._state["next"] = target
        return self

    def build(self) -> AssignStep:
        items = self._state["items"]
        if not items:
            raise ValueError("Assign builder has no items — call .set() or .items()")
        return AssignStep(assign=items, next=self._state["next"])


# ============================================================================
# Call
# ============================================================================


class Call(StepBase):
    """Builder for CallStep.

    Internal state keys:
        func   : str               — function name
        args   : Dict | None       — call arguments
        result : str | None        — result variable name
        next   : str | None        — jump target

    Usage::

        Call("sys.log").args(text="hello").build()
    """

    def __init__(self, function: str = "") -> None:
        super().__init__()
        if function:
            self._state["func"] = function

    def func(self, name: str) -> Call:
        """Set or overwrite the function to call."""
        self._state["func"] = name
        return self

    def args(self, **kwargs: Any) -> Call:
        """Set the call arguments."""
        self._state["args"] = kwargs
        return self

    def result(self, name: str) -> Call:
        """Set the result variable name."""
        self._state["result"] = name
        return self

    def next(self, target: str) -> Call:
        """Set the 'next' jump target."""
        self._state["next"] = target
        return self

    def build(self) -> CallStep:
        func = self._state.get("func", "")
        if not func:
            raise ValueError(
                "Call builder has no function — call .func() or pass it to constructor"
            )
        return CallStep(
            call=func,
            args=self._state.get("args"),
            result=self._state.get("result"),
            next=self._state.get("next"),
        )

    def apply(self, source: Any) -> Call:
        """Merge another Call builder — overwrites only fields the source has set.

        Unlike the default deep-merge, Call treats each field as a scalar
        (args is replaced wholesale, not recursively merged).
        """
        resolved = _resolve_source(source, Call, "Call")
        if resolved is None:
            return self
        for key, value in resolved._state.items():
            self._state[key] = deepcopy(value)
        return self


# ============================================================================
# Return_
# ============================================================================


class Return_(StepBase):
    """Builder for ReturnStep.

    Internal state keys:
        value : Any  — the return value

    Usage::

        Return_("ok").build()
        Return_(expr("x + y")).build()
    """

    def __init__(self, val: Any = None, *, _has_value: bool = False) -> None:
        super().__init__()
        if val is not None or _has_value:
            self._state["value"] = val

    def value(self, v: Any) -> Return_:
        """Set the return value."""
        self._state["value"] = v
        return self

    def build(self) -> ReturnStep:
        if not self.has("value"):
            raise ValueError(
                "Return_ builder has no value — call .value() or pass it to constructor"
            )
        return ReturnStep(return_=self._state["value"])


# ============================================================================
# Raise_
# ============================================================================


class Raise_(StepBase):
    """Builder for RaiseStep.

    Internal state keys:
        value : Any  — the raise value

    Usage::

        Raise_({"code": 404}).build()
        Raise_(expr("e")).build()
    """

    def __init__(self, val: Any = None, *, _has_value: bool = False) -> None:
        super().__init__()
        if val is not None or _has_value:
            self._state["value"] = val

    def value(self, v: Any) -> Raise_:
        """Set the raise value."""
        self._state["value"] = v
        return self

    def build(self) -> RaiseStep:
        if not self.has("value"):
            raise ValueError(
                "Raise_ builder has no value — call .value() or pass it to constructor"
            )
        return RaiseStep(raise_=self._state["value"])


# ============================================================================
# Switch
# ============================================================================


class Switch(StepBase):
    """Builder for SwitchStep.

    Internal state keys:
        conditions : List[Dict[str, Any]]  — switch conditions
        next       : str | None            — fallthrough target

    Usage::

        Switch()
            .condition(expr("x > 0"), next="positive")
            .condition(True, next="negative")
            .build()
    """

    def __init__(self) -> None:
        super().__init__(conditions=[], next=None)

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
            entry["steps"] = steps
        if assign is not None:
            entry["assign"] = assign
        if return_ is not _UNSET:
            entry["return"] = return_
        if raise_ is not _UNSET:
            entry["raise"] = raise_
        self._state["conditions"].append(entry)
        return self

    def next(self, target: str) -> Switch:
        """Set the 'next' fallthrough target."""
        self._state["next"] = target
        return self

    def build(self) -> SwitchStep:
        conditions_raw = self._state["conditions"]
        if not conditions_raw:
            raise ValueError("Switch builder has no conditions — call .condition()")

        from .builder import StepBuilder

        conditions = []
        for entry in conditions_raw:
            raw_steps = entry.get("steps")
            if raw_steps is not None:
                if isinstance(raw_steps, StepBuilder) or callable(raw_steps):
                    entry = dict(entry)
                    entry["steps"] = _resolve_step_builder(raw_steps)
            conditions.append(SwitchCondition(**entry))
        return SwitchStep(switch=conditions, next=self._state["next"])


# ============================================================================
# For
# ============================================================================


class For(StepBase):
    """Builder for ForStep.

    Internal state keys:
        value : str           — loop variable name
        in    : Any           — collection to iterate
        range : Any           — range to iterate
        index : str | None    — index variable name
        steps : Any           — loop body (StepBuilder, callable, or list)

    Usage::

        For("item").in_(["a", "b"]).steps(step_builder).build()
    """

    def __init__(self, value: str = "") -> None:
        super().__init__(value=value)

    def value(self, name: str) -> For:
        """Set the loop variable name."""
        self._state["value"] = name
        return self

    def in_(self, items: Any) -> For:
        """Set the collection to iterate over."""
        self._state["in"] = items
        return self

    def range_(self, r: Any) -> For:
        """Set the range to iterate over."""
        self._state["range"] = r
        return self

    def index(self, name: str) -> For:
        """Set the index variable name."""
        self._state["index"] = name
        return self

    def steps(self, sb: Any) -> For:
        """Set the loop body steps (a StepBuilder, callable, or list)."""
        self._state["steps"] = sb
        return self

    def build(self) -> ForStep:
        val = self._state.get("value", "")
        if not val:
            raise ValueError(
                "For builder has no value variable — pass it to constructor or call .value()"
            )
        if not self.has("steps"):
            raise ValueError("For builder has no steps — call .steps()")

        step_dicts = _resolve_step_builder(self._state["steps"])

        return ForStep(
            for_=ForBody(
                value=val,
                index=self._state.get("index"),
                in_=self._state.get("in"),
                range=self._state.get("range"),
                steps=step_dicts,
            )
        )


# ============================================================================
# Parallel
# ============================================================================


class Parallel(StepBase):
    """Builder for ParallelStep.

    Internal state keys:
        branches         : List[Tuple[str, Any]]  — (name, steps) pairs
        shared           : List[str] | None
        exception_policy : str | None
        concurrency_limit: int | str | None

    Usage::

        Parallel()
            .branch("b1", step_builder_1)
            .branch("b2", step_builder_2)
            .build()
    """

    def __init__(self) -> None:
        super().__init__(branches=[])

    def branch(self, name: str, steps: Any) -> Parallel:
        """Add a parallel branch."""
        self._state["branches"].append((name, steps))
        return self

    def shared(self, vars: List[str]) -> Parallel:
        """Set shared variable names."""
        self._state["shared"] = vars
        return self

    def exception_policy(self, policy: str) -> Parallel:
        """Set exception policy (e.g. 'continueAll')."""
        self._state["exception_policy"] = policy
        return self

    def concurrency_limit(self, limit: Union[int, str]) -> Parallel:
        """Set concurrency limit."""
        self._state["concurrency_limit"] = limit
        return self

    def build(self) -> ParallelStep:
        branch_list = self._state.get("branches", [])
        if not branch_list:
            raise ValueError("Parallel builder has no branches — call .branch()")

        branches = []
        for name, steps in branch_list:
            step_dicts = _resolve_step_builder(steps)
            branches.append(Branch(name=name, steps=step_dicts))

        return ParallelStep(
            parallel=ParallelBody(
                branches=branches,
                shared=self._state.get("shared"),
                exception_policy=self._state.get("exception_policy"),
                concurrency_limit=self._state.get("concurrency_limit"),
            )
        )


# ============================================================================
# Try_
# ============================================================================


class Try_(StepBase):
    """Builder for TryStep.

    Internal state keys:
        body         : Any           — try body (StepBuilder, callable, or model)
        retry        : Dict | str    — retry configuration
        except_as    : str | None    — except variable name
        except_steps : Any           — except handler steps

    Usage::

        Try_(body_step_builder)
            .retry(predicate=expr("e.code == 429"), max_retries=3, backoff={...})
            .except_(as_="e", steps=except_step_builder)
            .build()
    """

    def __init__(self, body: Any = None) -> None:
        super().__init__()
        if body is not None:
            self._state["body"] = body

    def body(self, sb: Any) -> Try_:
        """Set the try body (a StepBuilder, callable, or model)."""
        self._state["body"] = sb
        return self

    def retry(
        self,
        *,
        predicate: str,
        max_retries: int,
        backoff: Dict[str, Any],
    ) -> Try_:
        """Set retry configuration."""
        self._state["retry"] = {
            "predicate": predicate,
            "max_retries": max_retries,
            "backoff": backoff,
        }
        return self

    def except_(self, *, as_: str, steps: Any) -> Try_:
        """Set except handler."""
        self._state["except_as"] = as_
        self._state["except_steps"] = steps
        return self

    def build(self) -> TryStep:
        if not self.has("body"):
            raise ValueError(
                "Try_ builder has no body — call .body() or pass it to constructor"
            )

        from .builder import StepBuilder

        # Resolve callable body to StepBuilder first
        body = self._state["body"]
        if callable(body) and not isinstance(body, StepBuilder):
            sb = StepBuilder()
            body(sb)
            body = sb

        # Determine try body type
        if isinstance(body, StepBuilder):
            body_steps = body.build()
            if len(body_steps) == 1:
                body_model = body_steps[0].body
                if isinstance(body_model, CallStep):
                    try_body = TryCallBody(
                        call=body_model.call,
                        args=body_model.args,
                        result=body_model.result,
                    )
                else:
                    try_body = TryStepsBody(steps=_resolve_step_builder(body))
            else:
                try_body = TryStepsBody(steps=_resolve_step_builder(body))
        else:
            try_body = body

        # Resolve retry
        retry = None
        retry_raw = self._state.get("retry")
        if retry_raw is not None:
            if isinstance(retry_raw, dict):
                backoff_data = retry_raw["backoff"]
                if isinstance(backoff_data, dict):
                    backoff = BackoffConfig(**backoff_data)
                else:
                    backoff = backoff_data
                retry = RetryConfig(
                    predicate=retry_raw["predicate"],
                    max_retries=retry_raw["max_retries"],
                    backoff=backoff,
                )
            elif isinstance(retry_raw, str):
                retry = retry_raw
            else:
                retry = retry_raw

        # Resolve except
        except_body = None
        except_as = self._state.get("except_as")
        except_steps = self._state.get("except_steps")
        if except_as is not None and except_steps is not None:
            except_step_dicts = _resolve_step_builder(except_steps)
            except_body = ExceptBody(as_=except_as, steps=except_step_dicts)

        return TryStep(
            try_=try_body,
            retry=retry,
            except_=except_body,
        )


# ============================================================================
# Steps (nested steps)
# ============================================================================


class Steps(StepBase):
    """Builder for NestedStepsStep.

    Internal state keys:
        body : Any           — nested steps (StepBuilder, callable, or list)
        next : str | None    — jump target

    Usage::

        Steps(inner_step_builder).next("done").build()
    """

    def __init__(self, body: Any = None) -> None:
        super().__init__()
        if body is not None:
            self._state["body"] = body

    def body(self, sb: Any) -> Steps:
        """Set the nested steps body (a StepBuilder, callable, or list)."""
        self._state["body"] = sb
        return self

    def next(self, target: str) -> Steps:
        """Set the 'next' jump target."""
        self._state["next"] = target
        return self

    def build(self) -> NestedStepsStep:
        if not self.has("body"):
            raise ValueError(
                "Steps builder has no body — call .body() or pass it to constructor"
            )

        step_dicts = _resolve_step_builder(self._state["body"])

        return NestedStepsStep(steps=step_dicts, next=self._state.get("next"))


# ============================================================================
# Aliases — friendlier names that avoid trailing underscores
# ============================================================================

Returns = Return_
"""Alias for :class:`Return_`."""

DoReturn = Return_
"""Alias for :class:`Return_`."""

Raises = Raise_
"""Alias for :class:`Raise_`."""

DoRaise = Raise_
"""Alias for :class:`Raise_`."""

DoTry = Try_
"""Alias for :class:`Try_`."""

Loop = For
"""Alias for :class:`For`."""
