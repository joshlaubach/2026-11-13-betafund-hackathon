"""Verified parametric and polar calculus problems; called only by the sandbox worker.

The model proposes the curve (and the point, interval or question); the server derives every derivative, area and
length with SymPy and checks it against an independent numeric computation (difference quotients, polylines)."""
from app.calc2 import parametric, polar
from app.shared.integral_core import Reject

# Stems: parametric_area, parametric_arc_length, parametric_surface_area, polar_area and polar_arc_length are renamed so that no two topics
# (and not calc.applications.arc_length, owned by C5b) share a stem; see app/catalog/__init__.py.
RUNNERS = {
    "tangents": parametric.tangents, "second_derivatives": parametric.second_derivatives,
    "parametric_area": parametric.parametric_area, "parametric_arc_length": parametric.parametric_arc_length,
    "parametric_surface_area": parametric.surface_area, "slopes": polar.slopes, "polar_area": polar.polar_area,
    "polar_arc_length": polar.polar_arc_length,
}
TOPICS = tuple(RUNNERS)
VERIFIER = {stem: "calc." + name for stem, name in (
    ("tangents", "parametric_tangents"), ("second_derivatives", "parametric_second_derivatives"),
    ("parametric_area", "parametric_area"), ("parametric_arc_length", "parametric_arc_length"),
    ("parametric_surface_area", "parametric_surface_area"), ("slopes", "polar_slopes"),
    ("polar_area", "polar_area"), ("polar_arc_length", "polar_arc_length"))}
FIELDS = {   # payload fields (the model's reply), required then optional
    "tangents": (("x", "y", "t0", "ask"), ("t1",)),
    "second_derivatives": (("x", "y", "ask"), ("t0",)),
    "parametric_area": (("x", "y", "t0", "t1"), ()),
    "parametric_arc_length": (("x", "y", "t0", "t1"), ()),
    "parametric_surface_area": (("x", "y", "t0", "t1", "axis"), ()),
    "slopes": (("r", "t0", "ask"), ("t1",)),
    "polar_area": (("r", "t0", "t1"), ("r2",)),
    "polar_arc_length": (("r", "t0", "t1"), ()),
}


def verify(topic, bounds=None, axes=None, calculator="none", **fields):
    try:
        if topic not in RUNNERS:
            raise Reject("slip", "unknown parametric/polar topic")
        if bounds is not None:
            raise Reject("slip", "parametric and polar payloads do not use bounds")
        if calculator not in ("none", "scientific"):
            raise Reject("slip", "unsupported calculator tier")
        required, optional = FIELDS[topic]
        if set(fields) - set(required) - set(optional):
            raise Reject("slip", "unexpected payload field")
        return RUNNERS[topic](**fields, axes=axes or {}, calculator=calculator)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap}
