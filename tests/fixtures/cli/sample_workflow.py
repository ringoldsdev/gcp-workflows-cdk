"""Sample workflow definition file for CLI tests."""

from cloud_workflows import StepBuilder, WorkflowBuilder, expr


def run():
    steps = (
        StepBuilder()
        .step("init", "assign", x=10, y=20)
        .step("done", "return", value=expr("x + y"))
    )
    return [("sample.yaml", WorkflowBuilder().workflow("main", steps).build())]
