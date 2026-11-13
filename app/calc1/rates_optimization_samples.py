"""Offline source of related rates and optimization word problems (C3 milestone b, second half). Each row is a reply
in the shape of the model's JSON (statement, relations, givens, unknown, params) written from a template, so the blind
re-solve is skipped (the pipeline sees raw=None); the structure still goes through app.shared.wordproblem.verify and the
calculus methods in app/calc1/rates_optimization.py like a model reply."""
import itertools
import random

from app.shared import wordproblem

METHOD = {"related_rates": "related_rates", "optimization": "optimize"}
MODULE = "app.calc1.rates_optimization"


def _g(name, value, unit):
    return {"name": name, "value": str(value), "text": str(value), "unit": unit}


def _row(statement, relations, givens, unknown, unit, params):
    return {"statement": statement, "relations": relations, "givens": givens,
            "unknown": {"name": unknown, "unit": unit}, "params": [{"key": k, "value": v} for k, v in params]}


# -- related rates -------------------------------------------------------------------------------------------------

def _circle():
    rows = []
    rel, par = ["A = pi*r^2", "w = 2*pi*r*u"], [("w", "A"), ("u", "r")]
    for r, u in itertools.product((2, 3, 4, 5, 6, 8, 10), (2, 3, 4, 5)):
        rows.append(("circle", _row(
            f"The radius of a circular oil slick is growing at {u} meters per minute. How fast is the area of the slick "
            f"growing at the instant when the radius is {r} meters?", rel,
            [_g("r", r, "m"), _g("u", u, "m/min")], "w", "m^2/min", par)))
    for r, w in itertools.product((2, 3, 4, 5, 6, 10), (6, 10, 12, 20, 24, 40)):
        rows.append(("circle", _row(
            f"The area of a circular oil slick is growing at {w} square meters per minute. How fast is the radius of the "
            f"slick growing at the instant when the radius is {r} meters?", rel,
            [_g("r", r, "m"), _g("w", w, "m^2/min")], "u", "m/min", par)))
    return rows


def _sphere():
    rows = []
    rel, par = ["V = 4*pi*r^3/3", "w = 4*pi*r^2*u"], [("w", "V"), ("u", "r")]
    for r, u in itertools.product((2, 3, 4, 5, 6), (2, 3, 4, 5)):
        rows.append(("sphere", _row(
            f"A spherical balloon is being inflated so that its radius grows at {u} centimeters per second. How fast is "
            f"the volume of the balloon increasing at the instant when the radius is {r} centimeters?", rel,
            [_g("r", r, "cm"), _g("u", u, "cm/s")], "w", "cm^3/s", par)))
    for r, w in itertools.product((2, 3, 4, 5, 6), (4, 8, 12, 16, 36, 100)):
        rows.append(("sphere", _row(
            f"Air is pumped into a spherical balloon so that its volume grows at {w} cubic centimeters per second. How fast "
            f"is the radius growing at the instant when the radius is {r} centimeters?", rel,
            [_g("r", r, "cm"), _g("w", w, "cm^3/s")], "u", "cm/s", par)))
    return rows


def _ladder():
    rows = []
    rel, par = ["x^2 + y^2 = z^2", "x*u = y*v"], [("u", "x"), ("v", "-y")]
    for (z, x, y), u in itertools.product(((10, 6, 8), (10, 8, 6), (13, 5, 12), (13, 12, 5), (15, 9, 12), (15, 12, 9),
                                           (17, 8, 15), (17, 15, 8), (25, 7, 24), (25, 15, 20), (25, 20, 15)), (2, 3, 4)):
        rows.append(("ladder", _row(
            f"A {z}-foot ladder leans against a vertical wall. The bottom of the ladder is pulled away from the wall at {u} "
            f"feet per second. How fast is the top of the ladder sliding down the wall at the instant when the bottom is {x} "
            f"feet from the wall?", rel, [_g("z", z, "ft"), _g("x", x, "ft"), _g("u", u, "ft/s")], "v", "ft/s", par)))
        rows.append(("ladder", _row(
            f"A {z}-foot ladder leans against a vertical wall. The top of the ladder slides down the wall at {u} feet per "
            f"second. How fast is the bottom of the ladder moving away from the wall at the instant when the top is {y} "
            f"feet above the ground?", rel, [_g("z", z, "ft"), _g("y", y, "ft"), _g("v", u, "ft/s")], "u", "ft/s", par)))
    return rows


def _cars():
    rows = []
    rel, par = ["s^2 = x^2 + y^2", "s*w = x*u + y*v"], [("u", "x"), ("v", "y"), ("w", "s")]
    for (x, y), u, v in itertools.product(((3, 4), (6, 8), (5, 12), (9, 12), (8, 15), (12, 5), (30, 40), (20, 21)),
                                          (20, 30, 40, 60), (10, 25, 50)):
        rows.append(("two_cars", _row(
            f"Car A is {x} miles east of an intersection and driving east at {u} miles per hour. Car B is {y} miles north of "
            f"the intersection and driving north at {v} miles per hour. At what rate is the distance between the two cars "
            f"increasing at that instant?", rel,
            [_g("x", x, "mi"), _g("y", y, "mi"), _g("u", u, "mph"), _g("v", v, "mph")], "w", "mph", par)))
    return rows


def _shadow():
    rows = []
    rel, par = ["H*s = p*(d + s)", "H*w = p*(u + w)"], [("u", "d"), ("w", "s")]
    for H, p, d, u in itertools.product((12, 15, 18, 20), (5, 6), (10, 12, 15, 20, 24), (2, 3, 4, 5, 6)):
        rows.append(("shadow", _row(
            f"A street lamp is {H} feet above the ground. A person {p} feet tall walks away from the base of the lamp at {u} "
            f"feet per second. How fast is the length of the person's shadow increasing at the instant when the person is {d} "
            f"feet from the base of the lamp?", rel,
            [_g("H", H, "ft"), _g("p", p, "ft"), _g("d", d, "ft"), _g("u", u, "ft/s")], "w", "ft/s", par)))
    return rows


def _cone():
    rows = []
    rel = ["V = pi*r^2*h/3", "r = h/2", "w = pi*(2*r*h*u + r^2*v)/3", "u = v/2"]
    par = [("w", "V"), ("u", "r"), ("v", "h")]
    for w, h in itertools.product((10, 20, 30, 40, 50, 60), (2, 3, 4, 5, 6, 8, 10)):
        rows.append(("cone_fill", _row(
            f"Water is poured into a tank shaped like a cone with its point down, at {w} cubic feet per minute. At every "
            f"moment the radius of the water's surface is half the depth of the water. How fast is the depth of the water "
            f"rising at the instant when the water is {h} feet deep?", rel,
            [_g("w", w, "ft^3/min"), _g("h", h, "ft")], "v", "ft/min", par)))
    return rows


# -- optimization --------------------------------------------------------------------------------------------------

def _fence():
    rows = []
    rel = ["2*x + 2*y = P", "A = x*y"]
    par = [("objective", "A"), ("goal", "max"), ("choose", "x")]
    for P in (40, 60, 80, 100, 120, 160, 200, 240):
        rows.append(("fence", _row(
            f"A farmer has {P} feet of fencing and wants to enclose a rectangular field. What is the largest area the field "
            f"can have?", rel, [_g("P", P, "ft")], "A", "ft^2", par)))
        rows.append(("fence", _row(
            f"A farmer has {P} feet of fencing and wants to enclose a rectangular field with the largest possible area. "
            f"What should the width of the field be?", rel, [_g("P", P, "ft")], "x", "ft", par)))
    return rows


def _fixed_area():
    rows = []
    rel = ["x*y = K", "P = 2*x + 2*y"]
    par = [("objective", "P"), ("goal", "min"), ("choose", "x")]
    for K in (16, 25, 36, 49, 64, 81, 100, 144, 225):
        rows.append(("fixed_area", _row(
            f"A rectangular garden must have an area of {K} square meters. What is the least amount of fencing that can "
            f"enclose it?", rel, [_g("K", K, "m^2")], "P", "m", par)))
        rows.append(("fixed_area", _row(
            f"A rectangular garden must have an area of {K} square meters and be enclosed with as little fencing as "
            f"possible. What should the width of the garden be?", rel, [_g("K", K, "m^2")], "x", "m", par)))
    return rows


def _river():
    rows = []
    rel = ["x*y = K", "F = 2*x + y"]
    par = [("objective", "F"), ("goal", "min"), ("choose", "x")]
    for m in (2, 3, 4, 5, 6, 7, 8, 10):
        K = 2 * m * m
        rows.append(("river", _row(
            f"A rancher will fence a rectangular pasture along a straight river, with no fence needed along the river. "
            f"The pasture must have an area of {K} square yards. What is the least amount of fencing needed?",
            rel, [_g("K", K, "yd^2")], "F", "yd", par)))
        rows.append(("river", _row(
            f"A rancher will fence a rectangular pasture along a straight river, with no fence needed along the river. "
            f"The pasture must have an area of {K} square yards, and the rancher wants to use as little fencing as possible. "
            f"How long should each of the two sides perpendicular to the river be?", rel, [_g("K", K, "yd^2")], "x", "yd", par)))
    return rows


def _box():
    rows = []
    rel = ["V = x*(L - 2*x)^2"]
    par = [("objective", "V"), ("goal", "max"), ("choose", "x"), ("domain", "0, L/2")]
    for L in (6, 12, 18, 24, 30, 36):
        rows.append(("box", _row(
            f"An open box is made from a square sheet of cardboard {L} inches on a side by cutting equal squares from the "
            f"four corners and folding up the sides. What is the largest volume the box can have?",
            rel, [_g("L", L, "inches")], "V", "cubic inches", par)))
        rows.append(("box", _row(
            f"An open box is made from a square sheet of cardboard {L} inches on a side by cutting equal squares from the "
            f"four corners and folding up the sides. What side length should the cut-out squares have to make the volume as "
            f"large as possible?", rel, [_g("L", L, "inches")], "x", "inches", par)))
    return rows


def _openbox():
    rows = []
    rel = ["V = x^2*h", "S = x^2 + 4*x*h"]
    par = [("objective", "S"), ("goal", "min"), ("choose", "x")]
    for V in (4, 32, 108, 256, 500):
        for unk, what, unit in (("S", "What is the least surface area (the base and the four sides) the box can have?", "ft^2"),
                                ("x", "What should the side length of the base be?", "ft"),
                                ("h", "What should the height of the box be?", "ft")):
            rows.append(("openbox", _row(
                f"A box with a square base and no lid must hold {V} cubic feet. To use as little material as possible, "
                f"the surface area must be as small as possible. {what}", rel, [_g("V", V, "ft^3")], unk, unit, par)))
    return rows


# Same structure as the circle and the sphere, told as a different story (a different context is a different problem).

def _ripple():
    rows = []
    rel, par = ["A = pi*r^2", "w = 2*pi*r*u"], [("w", "A"), ("u", "r")]
    for r, u in itertools.product((2, 3, 4, 5, 6, 8, 10), (2, 3, 4)):
        rows.append(("ripple", _row(
            f"A pebble dropped into a pond sends out a circular ripple whose radius grows at {u} feet per second. How fast "
            f"is the area enclosed by the ripple growing at the instant when the radius is {r} feet?", rel,
            [_g("r", r, "ft"), _g("u", u, "ft/s")], "w", "ft^2/s", par)))
    for r, w in itertools.product((2, 3, 4, 5, 6, 10), (6, 10, 12, 20, 24)):
        rows.append(("ripple", _row(
            f"A pebble dropped into a pond sends out a circular ripple whose enclosed area grows at {w} square feet per "
            f"second. How fast is the radius of the ripple growing at the instant when the radius is {r} feet?", rel,
            [_g("r", r, "ft"), _g("w", w, "ft^2/s")], "u", "ft/s", par)))
    return rows


def _bubble():
    rows = []
    rel, par = ["V = 4*pi*r^3/3", "w = 4*pi*r^2*u"], [("w", "V"), ("u", "r")]
    for r, u in itertools.product((2, 3, 4, 5), (2, 3, 4)):
        rows.append(("bubble", _row(
            f"A soap bubble is blown so that its radius grows at {u} millimeters per second. How fast is the volume of the "
            f"bubble increasing at the instant when the radius is {r} millimeters?", rel,
            [_g("r", r, "mm"), _g("u", u, "mm/s")], "w", "mm^3/s", par)))
    for r, w in itertools.product((2, 3, 4, 5), (4, 8, 12, 16, 36, 100)):
        rows.append(("bubble", _row(
            f"A soap bubble is blown so that its volume grows at {w} cubic millimeters per second. How fast is the radius "
            f"growing at the instant when the radius is {r} millimeters?", rel,
            [_g("r", r, "mm"), _g("w", w, "mm^3/s")], "u", "mm/s", par)))
    return rows


_TRIPLES = ((3, 4, 5), (4, 3, 5), (6, 8, 10), (8, 6, 10), (5, 12, 13), (12, 5, 13), (9, 12, 15), (12, 9, 15), (8, 15, 17),
            (15, 8, 17), (20, 21, 29), (21, 20, 29))


def _plane():
    rows = []
    rel, par = ["s^2 = x^2 + h^2", "s*w = x*u"], [("u", "x"), ("w", "s")]
    for (h, x, s), u in itertools.product(_TRIPLES, (200, 300, 400, 500, 600)):
        rows.append(("plane", _row(
            f"A plane flies horizontally at an altitude of {h} miles at {u} miles per hour, passing directly over a radar "
            f"station. At the instant when the plane is {x} miles horizontally past the station, how fast is the distance "
            f"between the plane and the station increasing?", rel,
            [_g("h", h, "mi"), _g("x", x, "mi"), _g("u", u, "mph")], "w", "mph", par)))
    return rows


def _boat():
    rows = []
    rel, par = ["s^2 = x^2 + h^2", "s*w = x*u"], [("w", "-s"), ("u", "-x")]
    for (h, x, s), w in itertools.product(_TRIPLES, (2, 3, 4, 5)):
        rows.append(("boat", _row(
            f"A boat is pulled toward a dock by a rope that runs from the bow through a ring on the dock {h} feet above the "
            f"bow. The rope is pulled in at {w} feet per second. How fast is the boat approaching the dock at the instant "
            f"when the boat is {x} feet from the dock, measured horizontally?", rel,
            [_g("h", h, "ft"), _g("x", x, "ft"), _g("w", w, "ft/s")], "u", "ft/s", par)))
    return rows


def _box_volume():
    rows = []
    rel = ["V = l*w*h", "q = w*h*a + l*h*b - l*w*c"]
    par = [("a", "l"), ("b", "w"), ("c", "-h"), ("q", "V")]
    for (l, w, h), (a, b, c) in itertools.product(((4, 3, 2), (5, 4, 3), (6, 2, 5), (3, 3, 3), (10, 4, 2), (8, 5, 6)),
                                                  ((2, 3, 2), (3, 2, 4), (2, 4, 3), (4, 2, 2), (3, 3, 2), (2, 2, 4))):
        rows.append(("box_volume", _row(
            f"The length and the width of a rectangular box are increasing at {a} and {b} centimeters per second, while its "
            f"height is decreasing at {c} centimeters per second. At the instant when the length is {l} centimeters, the "
            f"width is {w} centimeters and the height is {h} centimeters, how fast is the volume changing? Give a negative "
            f"value if the volume is decreasing.", rel,
            [_g("l", l, "cm"), _g("w", w, "cm"), _g("h", h, "cm"), _g("a", a, "cm/s"), _g("b", b, "cm/s"), _g("c", c, "cm/s")],
            "q", "cm^3/s", par)))
    return rows


def _angle():
    rows = []
    rel, par = ["h = d*tan(a)", "u = d*w/cos(a)^2"], [("u", "h"), ("w", "a")]
    for d, h, u in itertools.product((20, 30, 40, 60), (15, 20, 30, 45, 80), (2, 3, 4, 5)):
        rows.append(("balloon_angle", _row(
            f"A balloon rises straight up from level ground at {u} meters per second. An observer stands {d} meters from the "
            f"point where the balloon was released and watches it. How fast is the observer's angle of elevation to the "
            f"balloon, in radians per second, increasing at the instant when the balloon is {h} meters high?", rel,
            [_g("d", d, "m"), _g("h", h, "m"), _g("u", u, "m/s")], "w", "rad/s", par)))
    return rows


def _numbers():
    rows = []
    rel = ["x + y = S", "P = x*y"]
    par = [("objective", "P"), ("goal", "max"), ("choose", "x")]
    for S in (10, 20, 30, 40, 60, 100):
        rows.append(("numbers", _row(
            f"Two positive numbers add up to {S}. What is the largest possible value of their product?", rel,
            [_g("S", S, "")], "P", "", par)))
        rows.append(("numbers", _row(
            f"Two positive numbers add up to {S}, and their product is as large as possible. What is the value of each "
            f"number?", rel, [_g("S", S, "")], "x", "", par)))
    return rows


def _rows(*fns):
    out = []
    for fn in fns:
        out += fn()
    return out


TABLES = {
    "related_rates": {"rr_area": _rows(_circle, _sphere, _ripple, _bubble), "rr_ladder": _rows(_ladder),
                      "rr_plane": _rows(_plane), "rr_boat": _rows(_boat), "rr_cars": _rows(_cars),
                      "rr_shadow": _rows(_shadow), "rr_box": _rows(_box_volume), "rr_cone": _rows(_cone),
                      "rr_angle": _rows(_angle)},
    "optimization": {"op_numbers": _rows(_numbers), "op_fence": _rows(_fence), "op_area": _rows(_fixed_area),
                     "op_river": _rows(_river), "op_box": _rows(_box), "op_openbox": _rows(_openbox)},
}


def structure(payload: dict) -> dict:
    """A reply's structure in the shape wordproblem.verify takes (params as a dict)."""
    return {**payload, "params": wordproblem._params(payload)}


def generate(stem: str, recipe: dict, axes: dict, answers: set[str], calculator: str = "none", seed: int = 0,
             limit: int = 150) -> dict | None:
    rng = random.Random(seed)
    rows = [p for ctx, p in TABLES[stem].get(recipe["id"], []) if "context" not in axes or axes["context"] == ctx]
    rng.shuffle(rows)
    full = {"recipe": recipe["id"], **axes}
    for payload in rows[:limit]:
        r = wordproblem.verify(structure(payload), axes=full, calculator=calculator, method=METHOD[stem],
                               method_module=MODULE)
        if r["ok"] and r["answer"]["type"] in answers:
            return {"payload": payload, "result": {**r, "integrand": "; ".join(payload["relations"])}}   # for the packet files
    return None
