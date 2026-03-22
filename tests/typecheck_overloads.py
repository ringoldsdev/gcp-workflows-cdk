"""Type-check test for StepBuilder per-type methods.

This file is not run as a test — it is checked by pyright to verify
that all method signatures resolve correctly.
"""

from cloud_workflows import (
    StepBuilder,
    Assign,
    Call,
    Return_,
    Raise_,
    Switch,
    For,
    Parallel,
    Try_,
    Steps,
)
from cloud_workflows.models import AssignStep, ReturnStep, expr

sb = StepBuilder()

# assign with shorthand kwargs (arbitrary variable names)
sb.assign("init", x=10, y=20)

# assign with items
sb.assign("init2", items=[{"x": 10}])

# assign with lambda
sb.assign("init3", lambda a: a.set("x", 10))

# call with kwargs
sb.call("c1", func="sys.log", args={"text": "hi"})

# call with lambda
sb.call("c2", lambda c: c.func("sys.log").args(text="hi"))

# return with kwargs
sb.return_("r1", value="ok")

# return with lambda
sb.return_("r2", lambda r: r.value("ok"))

# raise with kwargs
sb.raise_("e1", value="err")

# raise with lambda
sb.raise_("e2", lambda r: r.value("err"))

# switch with kwargs
sb.switch("sw1", conditions=[{"condition": True, "next": "end"}])

# switch with lambda
sb.switch("sw2", lambda s: s.condition(True, next="end"))

# for with kwargs
sb.for_("f1", value="item", in_=["a", "b"], steps=StepBuilder())

# for with lambda + value kwarg
sb.for_("f2", lambda f: f.in_(["a"]).steps(StepBuilder()), value="item")

# parallel with kwargs
sb.parallel("p1", branches={"b1": StepBuilder(), "b2": StepBuilder()})

# parallel with lambda
sb.parallel("p2", lambda p: p.branch("b1", StepBuilder()).branch("b2", StepBuilder()))

# try with kwargs
sb.try_("t1", body=StepBuilder())

# try with lambda
sb.try_("t2", lambda t: t.body(StepBuilder()))

# nested_steps with kwargs
sb.nested_steps("n1", body=StepBuilder(), next="end")

# nested_steps with lambda
sb.nested_steps("n2", lambda s: s.body(StepBuilder()).next("end"))

# raw passthrough: dict
sb.raw("r_dict", {"assign": [{"x": 1}]})

# raw passthrough: Pydantic model
sb.raw("r_model", AssignStep(assign=[{"x": 1}]))

# raw passthrough: sub-builder
sb.raw("r_sub", Assign().set("x", 1))

# apply
sb.apply(StepBuilder())
sb.apply(lambda: StepBuilder())
