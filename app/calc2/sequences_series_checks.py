"""Independent numeric checks for sequence and series verifiers."""
import mpmath as mp
import sympy as sp

n = sp.Symbol("n", integer=True, positive=True)
a = sp.Symbol("a", real=True)


def _close(got, want, tol=1e-8):
    return abs(got - want) <= tol * max(1, abs(want))


def sequence(term, start, verdict, value=None, recurrence=False, meta=None):
    """Check a sequence by high-precision samples or recurrence iteration."""
    mp.mp.dps = 50
    meta = meta or {}
    want = mp.mpf(str(sp.N(value, 50))) if value is not None else None
    if recurrence:
        cur = mp.mpf(str(sp.N(start, 50)))
        fn = sp.lambdify(a, term, "mpmath")
        vals = []
        for _ in range(120):
            cur = fn(cur)
            vals.append(cur)
        if verdict == "converges":
            ok = _close(vals[-1], want, 1e-10)
            return ok, f"iteration {mp.nstr(vals[-1], 12)} vs {mp.nstr(want, 12)}"
        spread = max(abs(vals[-1] - vals[-2]), abs(vals[-1] - vals[-3]))
        growing = abs(vals[-1]) > 10 * max(1, abs(vals[0]))
        return bool(spread > mp.mpf("1e-6") or growing), f"late spread {mp.nstr(spread, 8)}"

    fn = sp.lambdify(n, term, "mpmath")
    if verdict == "converges":
        if meta.get("family") == "alternating":
            k = 10 ** 8
            got = (fn(k) + fn(k + 1)) / 2
            err = max(abs(fn(k) - want), abs(fn(k + 1) - want))
            return bool(err < mp.mpf("2e-3")), f"two subsequences within {mp.nstr(err, 8)}"
        try:
            got = mp.limit(fn, mp.inf)
        except (ValueError, ZeroDivisionError, ArithmeticError):
            got = fn(10 ** 8)
        return _close(got, want, 1e-7), f"numeric limit {mp.nstr(got, 12)} vs {mp.nstr(want, 12)}"
    k = 100 if meta.get("family") == "exponential" else 10 ** 6
    vals = [fn(k + j) for j in range(4)]
    separated = max(abs(vals[i] - vals[j]) for i in range(4) for j in range(i)) > mp.mpf("1e-3")
    growing = abs(fn(2 * k)) > abs(fn(k)) * mp.mpf("1.2") or abs(fn(k)) > 100
    return bool(separated or growing), f"late values {[mp.nstr(v, 6) for v in vals]}"


def series(term, start, verdict, value=None, meta=None):
    """Check a series with mpmath partial sums and a proved tail/growth bound."""
    mp.mp.dps = 50
    meta = meta or {}
    fn = sp.lambdify(n, term, "mpmath")
    kind = meta["family"]
    if kind == "geometric":
        r = mp.mpf(meta["ratio"])
        first = fn(start)
        if verdict == "diverges":
            lower = abs(first) * abs(r) ** 40
            return bool(abs(r) >= 1 and lower >= abs(first)), f"term lower bound at 40: {mp.nstr(lower, 8)}"
        count = 80
        partial = mp.fsum(fn(start + j) for j in range(count))
        tail = abs(first) * abs(r) ** count / (1 - abs(r))
    elif kind == "telescoping":
        if meta.get("radical"):
            gap = int(meta["gap"])
            partial = mp.fsum(fn(start + j) for j in range(5000))
            lower = abs(mp.mpf(meta["coefficient"])) * (mp.sqrt(start + 5000 + gap) - mp.sqrt(start + gap))
            return bool(verdict == "diverges" and abs(partial) >= lower / 2), f"growth lower bound {mp.nstr(lower, 8)}"
        count = 5000
        partial = mp.fsum(fn(start + j) for j in range(count))
        c = abs(mp.mpf(meta["coefficient"]))
        shift, gap, power = int(meta["shift"]), int(meta["gap"]), int(meta["power"])
        tail = c * mp.fsum(1 / mp.mpf(start + count + shift + j) ** power for j in range(gap))
    elif kind == "p_series":
        c, shift = mp.mpf(meta["coefficient"]), int(meta["shift"])
        p = mp.mpf(meta["power"])
        count = 5000
        partial = mp.fsum(fn(start + j) for j in range(count))
        if verdict == "diverges":
            end = start + count
            lower = c * (mp.log((end + shift) / (start + shift)) if p == 1 else
                         ((end + shift) ** (1 - p) - (start + shift) ** (1 - p)) / (1 - p))
            return bool(lower > 1), f"integral lower bound {mp.nstr(lower, 8)}"
        tail = c * mp.mpf(start + count + shift - 1) ** (1 - p) / (p - 1)
    else:
        return False, "unknown numeric-check family"
    if value is None:
        return bool(mp.isfinite(partial) and mp.isfinite(tail)), f"finite tail bound {mp.nstr(tail, 8)}"
    want = mp.mpf(str(sp.N(value, 50)))
    err = abs(want - partial)
    # lambdify can emit machine-precision rational coefficients even though
    # mpmath performs the summation.  Account for that evaluation roundoff;
    # the analytic tail remains the truncation-error bound.
    roundoff = mp.mpf("1e-14") * max(1, abs(want), abs(partial))
    return bool(err <= tail * (1 + mp.mpf("1e-10")) + roundoff), \
        f"partial error {mp.nstr(err, 8)}, tail bound {mp.nstr(tail, 8)}, roundoff {mp.nstr(roundoff, 8)}"


def audit(topic, payload, answer, raw):
    """Packet audit entry point. Parsing still happens in the sandbox worker."""
    from app.safe_parse import safe_parse

    recursive = topic == "recursive"
    symbol = a if recursive else n
    term = safe_parse(payload["term"], {symbol.name: symbol})
    start = safe_parse(payload["start"])
    value = safe_parse(answer["sympy"]) if answer.get("sympy") is not None else None
    verdict = raw["verdict"]
    if topic in ("limits", "monotone_bounded", "recursive"):
        ok, detail = sequence(term, start, verdict, value, recurrence=recursive, meta=raw)
        name = "P8 numeric sequence or recurrence check"
    else:
        ok, detail = series(term, int(start), verdict, value, meta=raw)
        name = "P8 mpmath partial sum with explicit tail/growth bound"
    return [[name, ok, detail]]
