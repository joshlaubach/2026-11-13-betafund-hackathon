"""Independent numerical checks for area and volume packet problems."""
import mpmath as mp
import sympy as sp

from app.shared.integral_core import _parse, x


def audit(integrand, answer, raw):
    mp.mp.dps = 40
    expr = _parse(integrand, x, "geometric integrand", depends=False)
    expected = _parse(answer["sympy"], x, "answer", depends=False)
    fn = sp.lambdify(x, expr, "mpmath")
    a, b = mp.mpf(raw["lower"]), mp.mpf(raw["upper"])
    cuts = [mp.mpf(v) for v in raw.get("cuts", [])] or [a, b]
    got = mp.quad(fn, cuts)
    want = complex(sp.N(expected, 35))
    ok = abs(complex(got) - want) <= 1e-7 * max(1, abs(want))
    return [("P8 independent quadrature agrees with the derived answer", ok, f"{got} vs {want}")]
