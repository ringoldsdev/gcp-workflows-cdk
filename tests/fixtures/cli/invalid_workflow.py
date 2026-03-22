"""Sample workflow definition that produces invalid output (for CLI error testing)."""

from cloud_workflows import StepBuilder, WorkflowBuilder, expr


def run():
    # References undefined variable 'z'
    steps = (
        StepBuilder()
        .step("init", "assign", x=10)
        .step("done", "return", value=expr("z"))
    )
    return [("invalid.yaml", WorkflowBuilder().workflow("main", steps).build())]
