"""Independent numeric packet checks, run inside the sandbox."""
import mpmath as mp
import sympy as sp

from app.integral_core import _parse, _bound, x


def audit(topic, payload, answer):
    mp.mp.dps = 35
    f = _parse(payload['f'], x, 'f', depends=False)
    want = _parse(answer['sympy'], x, 'answer', depends=False)
    fn = sp.lambdify(x, f, 'mpmath')
    out = []

    def number(s):
        return mp.mpf(str(sp.N(_bound(s, 'number'), 40)))

    def agrees(a, b):
        return bool(abs(complex(a)-complex(b)) <= 1e-7*max(1, abs(complex(b))))

    def check(label, got, expected):
        out.append((label, agrees(got, expected), f'{got} vs {expected}'))

    if topic in ('basic_antiderivatives', 'initial_value_problems'):
        F = sp.lambdify(x, want, 'mpmath')
        count = 0
        for t in (mp.mpf('.15'), mp.mpf('.3'), mp.mpf('.5'), mp.mpf('.7'), mp.mpf('.9'), mp.mpf('1.1'), mp.mpf('1.7'), mp.mpf('2.3'), mp.mpf('3.1')):
            try:
                a, b = mp.diff(F, t), fn(t)
                if abs(mp.im(a)) > 1e-10 or abs(mp.im(b)) > 1e-10 or not mp.isfinite(a+b):
                    continue
                check('P8 numerical derivative agrees with f', a, b)
                count += 1
            except (ValueError, ZeroDivisionError, TypeError):
                continue
        out.append(('P8 derivative checked at three real points', count >= 3, str(count)))
        if topic == 'initial_value_problems':
            check('P9 initial condition checked independently', F(number(payload['point'])), number(payload['value']))
        return out
    if topic == 'ftc_part1':
        g = sp.lambdify(x, _parse(payload['g'], x, 'g', depends=False), 'mpmath')
        h = sp.lambdify(x, _parse(payload['h'], x, 'h', depends=False), 'mpmath')
        A = lambda t: mp.quad(fn, [h(t), g(t)])
        actual = sp.lambdify(x, want, 'mpmath')
        for t in (mp.mpf('.2'), mp.mpf('.5'), mp.mpf('.8')):
            check('P8 derivative of numerical accumulation agrees', mp.diff(A,t), actual(t))
        return out
    if topic == 'definite_properties':
        total = number(payload['f'])
        left = number(payload['value']) if payload['mode'] != 'reverse' else mp.mpf(0)
        c = number(payload['n'])
        expected = {'reverse': lambda: -c*total, 'split': lambda: c*(total-left),
                    'combine': lambda: c*total+number(payload['point'])*left}[payload['mode']]()
        check('P8 given integral arithmetic checked independently', expected, number(answer['sympy']))
        return out
    b = payload['bounds']
    lo, hi = number(b['lower']), number(b['upper'])
    if topic == 'riemann_sums':
        n = int(payload['n'])
        width = (hi-lo)/n
        offset = {'left':mp.mpf(0), 'right':mp.mpf(1), 'midpoint':mp.mpf('.5')}[payload['mode']]
        expected = sum(fn(lo+(i+offset)*width)*width for i in range(n))
    elif topic == 'net_change_total_distance' and payload['mode'] == 'distance':
        roots = sp.Poly(f,x).sqf_part().nroots(maxsteps=100)
        cuts = [lo]+sorted(mp.mpf(str(sp.re(r))) for r in roots if abs(float(sp.im(r)))<1e-10 and lo<float(sp.re(r))<hi)+[hi]
        expected = mp.quad(lambda t: abs(fn(t)), cuts)
    else:
        expected = mp.quad(fn,[lo,(lo+hi)/2,hi])
        if topic == 'average_value':
            expected /= hi-lo
    check('P8 independent numeric computation agrees', expected, number(answer['sympy']))
    return out


def audit_recipe(topic, recipe, combinations):
    from app.integration_basics import verify
    results = []
    for axes in combinations:
        p = {k:str(v) for k,v in axes.items() if k not in ('lower','upper')}
        b = [str(axes['lower']),str(axes['upper'])] if 'lower' in axes else None
        r = verify(topic, bounds=b, axes={'recipe':recipe['id'], **axes}, **p)
        results.append({'ok':r['ok'], 'cap':r.get('cap'), 'reason':r.get('reason'),
                        'axes':axes, 'shape':r.get('shape')})
    return results
