"""Type-check test for StepBuilder.step() overloads.

This file is not run as a test — it is checked by pyright to verify
that all overloaded call signatures resolve correctly.
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

# Passthrough: dict
sb.step("s1", {"assign": [{"x": 1}]})

# Passthrough: Pydantic model
sb.step("s2", AssignStep(assign=[{"x": 1}]))

# Passthrough: sub-builder
sb.step("s3", Assign().set("x", 1))

# assign with shorthand kwargs (arbitrary variable names)
sb.step("init", "assign", x=10, y=20)

# assign with items
sb.step("init2", "assign", items=[{"x": 10}])

# assign with lambda
sb.step("init3", "assign", lambda a: a.set("x", 10))

# call with kwargs
sb.step("c1", "call", func="sys.log", args={"text": "hi"})

# call with lambda
sb.step("c2", "call", lambda c: c.func("sys.log").args(text="hi"))

# return with kwargs
sb.step("r1", "return", value="ok")

# return with lambda
sb.step("r2", "return", lambda r: r.value("ok"))

# raise with kwargs
sb.step("e1", "raise", value="err")

# raise with lambda
sb.step("e2", "raise", lambda r: r.value("err"))

# switch with kwargs
sb.step("sw1", "switch", conditions=[{"condition": True, "next": "end"}])

# switch with lambda
sb.step("sw2", "switch", lambda s: s.condition(True, next="end"))

# for with kwargs
sb.step("f1", "for", value="item", in_=["a", "b"], steps=[])

# for with lambda + value kwarg
sb.step("f2", "for", lambda f: f.in_(["a"]).steps(sb), value="item")

# parallel with kwargs
sb.step("p1", "parallel", branches={"b1": sb, "b2": sb})

# parallel with lambda
sb.step("p2", "parallel", lambda p: p.branch("b1", sb).branch("b2", sb))

# try with kwargs
sb.step("t1", "try", body=sb)

# try with lambda
sb.step("t2", "try", lambda t: t.body(sb))

# steps with kwargs
sb.step("n1", "steps", body=sb, next="end")

# steps with lambda
sb.step("n2", "steps", lambda s: s.body(sb).next("end"))
