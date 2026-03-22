"""Steps container and build() function for Cloud Workflows CDK.

``Steps`` is the universal container for workflow steps.  Steps are added
via the ``__call__`` protocol::

    s = Steps()
    s("init", Assign(x=10, y=20))
    s("log", Call("sys.log", args={"text": expr("x")}))
    s("done", Return(expr("x + y")))

``Steps`` instances are composable — merging steps from another container::

    common = Steps()
    common("log", Call("sys.log", args={"text": "starting"}))

    main = Steps()
    main(common)               # merges all steps from common
    main("done", Return("ok"))

For subworkflows with parameters, pass ``params`` to the constructor::

    helper = Steps(params=["input", {"timeout": 30}])
    helper("log", Call("sys.log", args={"text": expr("input")}))
    helper("done", Return("ok"))

Write to disk with ``build()``::

    build({"workflow.yaml": main})

If ``main`` is a ``Steps`` instance, ``build()`` auto-finalizes it into
a ``SimpleWorkflow`` or ``SubworkflowsWorkflow``.
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
from .steps import StepType

__all__ = [
    "Steps",
    "build",
]


# =============================================================================
# Steps — universal step container
# =============================================================================


class Steps:
    """Universal container for workflow steps.

    Steps are added via the ``__call__`` protocol, which is overloaded:

    * ``s("step_id", StepType)`` — add a single named step.
    * ``s(other_steps)`` — merge all steps from another ``Steps`` instance.

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

    def __call__(
        self,
        step_id_or_steps: Union[str, "Steps"],
        step: Optional[StepType] = None,
    ) -> None:
        """Add a step or merge steps from another container.

        Overloaded forms:

        * ``s("step_id", StepType)`` — add a named step.
        * ``s(other_steps)`` — merge all steps from another Steps container.
        """
        if isinstance(step_id_or_steps, Steps):
            if step is not None:
                raise TypeError(
                    "When merging Steps, pass only the Steps instance "
                    "(no second argument)"
                )
            self._steps.extend(step_id_or_steps._steps)
            return

        if isinstance(step_id_or_steps, str):
            if step is None:
                raise TypeError(f"Missing step type for step '{step_id_or_steps}'")
            if not isinstance(step, StepType):
                raise TypeError(
                    f"Expected a StepType instance, got {type(step).__name__}"
                )
            self._steps.append((step_id_or_steps, step))
            return

        raise TypeError(
            f"Expected step_id (str) or Steps instance, "
            f"got {type(step_id_or_steps).__name__}"
        )

    def build(self) -> List[Dict[str, Any]]:
        """Serialize all steps to a list of dicts for YAML output.

        Each entry is a single-key dict ``{step_id: <step_body>}``.
        """
        return [step.build(step_id) for step_id, step in self._steps]

    def __len__(self) -> int:
        return len(self._steps)

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
    workflows: Dict[str, Union[WorkflowModel, Steps, Dict[str, Steps]]],
    output_dir: Union[str, Path] = ".",
) -> List[Path]:
    """Build workflow definitions and write them to YAML files.

    ``workflows`` is a dict mapping filenames to workflow objects.

    Values can be:

    * A finalized model (``SimpleWorkflow`` or ``SubworkflowsWorkflow``).
    * A ``Steps`` instance (auto-finalized into ``SimpleWorkflow``).
    * A dict of ``{name: Steps}`` for multi-workflow files
      (auto-finalized into ``SubworkflowsWorkflow``).

    Args:
        workflows: Dict of ``{filename: workflow}``.
        output_dir: Directory to write files into. Defaults to ``"."``.

    Returns:
        List of ``Path`` objects for every file written.

    Example::

        s = Steps()
        s("init", Assign(x=10))
        s("done", Return(expr("x")))
        build({"flow.yaml": s})

        # Multi-workflow:
        main = Steps()
        main("call", Call("helper", result="r"))
        main("done", Return(expr("r")))
        helper = Steps(params=["input"])
        helper("done", Return("ok"))
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
        workflow = _finalize(workflow)

        if not isinstance(workflow, (SimpleWorkflow, SubworkflowsWorkflow)):
            raise TypeError(
                f"Workflow value must be SimpleWorkflow, SubworkflowsWorkflow, "
                f"Steps, or dict of Steps, got {type(workflow).__name__}"
            )

        path = out / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(workflow.to_yaml(), encoding="utf-8")
        written.append(path)

    return written


def _finalize(
    value: Any,
) -> Union[SimpleWorkflow, SubworkflowsWorkflow]:
    """Convert a build() value to a finalized workflow model.

    Handles:
    - Already-finalized models (passthrough).
    - ``Steps`` instances (single workflow).
    - ``dict[str, Steps]`` (multi-workflow).
    """
    if isinstance(value, (SimpleWorkflow, SubworkflowsWorkflow)):
        return value

    if isinstance(value, Steps):
        return value._finalize()

    if isinstance(value, dict):
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

    raise TypeError(
        f"Expected SimpleWorkflow, SubworkflowsWorkflow, Steps, or dict, "
        f"got {type(value).__name__}"
    )
