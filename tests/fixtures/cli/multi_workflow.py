"""Sample workflow that outputs multiple YAML files."""

from cloud_workflows import StepBuilder, WorkflowBuilder, expr


def run():
    flow1 = (
        StepBuilder()
        .step("init", "assign", x=1)
        .step("done", "return", value=expr("x"))
    )
    flow2 = (
        StepBuilder()
        .step("init", "assign", y=2)
        .step("done", "return", value=expr("y"))
    )
    return [
        ("flow1.yaml", WorkflowBuilder().workflow("main", flow1).build()),
        ("flow2.yaml", WorkflowBuilder().workflow("main", flow2).build()),
    ]
