"""Steps container and build() function for Cloud Workflows CDK.

``Steps`` is the universal container for workflow steps.  Steps are added
via the ``.step()`` method which supports chaining::

    s = Steps()
    s.step("init", Assign(x=10, y=20))
     .step("log", Call("sys.log", args={"text": expr("x")}))
     .step("done", Return(expr("x + y")))

``Steps`` instances are composable — merging steps from another container::

    common = Steps()
    common.step("log", Call("sys.log", args={"text": "starting"}))

    main = Steps()
    main.merge(common)                # merges all steps from common
    main.step("done", Return("ok"))

For subworkflows with parameters, pass ``params`` to the constructor::

    helper = Steps(params=["input", {"timeout": 30}])
    helper.step("log", Call("sys.log", args={"text": expr("input")}))
    helper.step("done", Return("ok"))

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

    Steps are added via the ``.step()`` method, which returns ``self``
    for chaining::

        s = Steps()
        s.step("init", Assign(x=10)).step("done", Return("ok"))

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
