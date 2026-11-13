"""Independent packet re-check from the generated Cartesian curve."""
import mpmath as mp
import sympy as sp

from app.shared.integral_core import _parse, x


def audit(answer, raw):
    curve = _parse(raw["curve"], x, "curve", depends=False)
    value = _parse(answer["sympy"], x, "answer", depends=False)
    derivative = sp.diff(curve, x)
    with mp.workdps(40):
        fn = sp.lambdify(x, sp.sqrt(1 + derivative**2), "mpmath")
        got = mp.quad(fn, [mp.mpf(raw["lower"]), mp.mpf(raw["upper"])])
        want = mp.mpf(str(sp.N(value, 40)))
        ok = abs(got - want) <= mp.mpf("1e-8") * max(1, abs(want))
    return [("P8 independent arc-length quadrature agrees", bool(ok), f"{got} vs {want}")]
