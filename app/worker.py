"""Child-process entry point for app.sandbox. Reads one JSON job on stdin."""
import json
import sys


def _limit_memory() -> None:
    try:
        import resource
    except ImportError:  # Windows dev machines
        return
    cap = 1024 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (cap, cap))


def parse(expr: str) -> dict:
    import sympy as sp
    from app.safe_parse import safe_parse
    e = safe_parse(expr)
    return {"str": str(e), "srepr": sp.srepr(e)}


def equivalent(a: str, b: str) -> bool:
    import sympy as sp
    from app.safe_parse import safe_parse
    return bool(sp.simplify(safe_parse(a) - safe_parse(b)) == 0)


def verify_usub(g: str, R: str, bounds: list[str] | None = None, trap: bool = False, axes: dict | None = None) -> dict:
    from app.usub import verify
    return verify(g, R, bounds, trap, axes)


def verify_by_parts(u: str, dv: str, rest: str | None = None, g: str | None = None, bounds: list[str] | None = None,
                    axes: dict | None = None, calculator: str = "none") -> dict:
    from app.by_parts import verify
    return verify(u, dv, rest, g, bounds, axes, calculator)


def _topic_task(module: str, **fixed):
    """A verifier task for a topic module whose `verify(**args)` takes the payload fields as keywords."""
    def run(**args):
        import importlib
        return importlib.import_module(module).verify(**fixed, **args)
    return run


def offline_generate(stem: str, recipe: dict, axes: dict, answers: list, calculator: str, seed: int) -> dict | None:
    """One sampler call, run in the sandbox so a hung SymPy call cannot block the server."""
    from app import offline
    got = offline.SAMPLERS[stem](recipe, axes, set(answers), calculator, seed=seed)
    return {"payload": offline.payload_for_reply(stem, got["payload"])} if got else None


def wordproblem_verify(**args) -> dict:
    from app import wordproblem
    return wordproblem.verify(**args)


def wordproblem_compare(**args) -> dict:
    from app import wordproblem
    return wordproblem.compare(**args)


def spin(seconds: float | None = None) -> str:
    """Probe/test task: burn CPU, forever if seconds is None."""
    import time
    end = time.monotonic() + seconds if seconds else float("inf")
    while time.monotonic() < end:
        pass
    return "done"


TASKS = {"parse": parse, "equivalent": equivalent, "verify_usub": verify_usub,
         "verify_by_parts": verify_by_parts, "spin": spin,
         "verify_trig_integrals": _topic_task("app.trigfam"),
         "verify_hyperbolic": _topic_task("app.trigfam", hyp=True),
         "verify_partial_fractions": _topic_task("app.partial_fractions"),
         "verify_trig_substitution": _topic_task("app.trig_substitution"),
         "verify_improper": _topic_task("app.improper"),
         "verify_rules": _topic_task("app.rules"),
         "verify_strategy": _topic_task("app.strategy"), "offline_generate": offline_generate,
         "verify_error_bounds": _topic_task("app.error_bounds"),
         "wordproblem_verify": wordproblem_verify, "wordproblem_compare": wordproblem_compare}
for _stem in ("algebraic", "one_sided", "infinite", "at_infinity", "squeeze", "epsilon_delta",
              "classify_discontinuity", "make_continuous", "ivt"):          # calc.limits.*, calc.continuity.*
    TASKS[f"verify_limits_{_stem}"] = _topic_task("app.limits", stem=_stem)
for _stem in ("difference_quotient", "rate_of_change", "limit_definition", "differentiability", "power_rule", "trig",
              "exponential_log", "inverse_trig", "dhyperbolic"):             # calc.derivatives.*, milestone (a)
    TASKS[f"verify_derivatives_{_stem}"] = _topic_task("app.derivatives", stem=_stem)
for _stem in ("product_rule", "quotient_rule", "chain_rule", "tangent_normal_lines"):     # C2 milestone (b)
    TASKS[f"verify_derivatives_{_stem}"] = _topic_task("app.derivative_rules", stem=_stem)
for _stem in ("implicit", "logarithmic", "inverse_functions", "higher_order"):             # C2 milestone (c)
    TASKS[f"verify_derivatives_{_stem}"] = _topic_task("app.derivative_advanced", stem=_stem)
for _stem in ("critical_numbers", "absolute_extrema", "increasing_decreasing", "relative_extrema", "rolle_mvt",
              "concavity_inflection", "curve_sketching"):                               # C3 milestone (a)
    TASKS[f"verify_applications_{_stem}"] = _topic_task("app.applications", stem=_stem)
for _stem in ("linear_approximation", "lhopital", "newtons_method", "motion", "marginal_analysis"):   # C3 milestone (b), no story
    TASKS[f"verify_applications_{_stem}"] = _topic_task("app.applications_b", stem=_stem)



from app.integration_basics import TOPICS as _BASICS_TOPICS
for _topic in _BASICS_TOPICS:
    TASKS["verify_" + _topic] = _topic_task("app.integration_basics", topic=_topic)

from app.integral_applications import TOPICS as _INTEGRAL_APPLICATION_TOPICS
for _topic in _INTEGRAL_APPLICATION_TOPICS:
    TASKS["verify_" + _topic] = _topic_task("app.integral_applications", topic=_topic)

TASKS["verify_arc_length"] = _topic_task("app.arc_length")


def audit_integration_basics(**args):
    from app.integration_basics_checks import audit
    return audit(**args)


def audit_integration_basics_recipe(**args):
    from app.integration_basics_checks import audit_recipe
    return audit_recipe(**args)


TASKS["audit_integration_basics"] = audit_integration_basics
TASKS["audit_integration_basics_recipe"] = audit_integration_basics_recipe


def audit_integral_applications(**args):
    from app.integral_applications_checks import audit
    return audit(**args)


TASKS["audit_integral_applications"] = audit_integral_applications


def audit_arc_length(**args):
    from app.arc_length_checks import audit
    return audit(**args)


TASKS["audit_arc_length"] = audit_arc_length


for _topic in ("limits", "monotone_bounded", "recursive", "geometric", "telescoping", "p_series"):
    TASKS["verify_sequences_series_" + _topic] = _topic_task("app.sequences_series", topic=_topic)


def audit_sequences_series(**args):
    from app.sequences_series_checks import audit
    return audit(**args)


TASKS["audit_sequences_series"] = audit_sequences_series


for _topic in ("convergence_tests", "integral_test_remainder", "alternating_error", "absolute_conditional"):
    TASKS["verify_series_tests_" + _topic] = _topic_task("app.series_tests", topic=_topic)


def audit_series_tests(**args):
    from app.series_tests_checks import audit
    return audit(**args)


TASKS["audit_series_tests"] = audit_series_tests

from app.parametric_polar import TOPICS as _PARAMETRIC_POLAR_TOPICS
for _topic in _PARAMETRIC_POLAR_TOPICS:
    TASKS["verify_parametric_polar_" + _topic] = _topic_task("app.parametric_polar", topic=_topic)


def audit_parametric_polar(**args):
    from app.parametric_polar_checks import audit
    return audit(**args)


TASKS["audit_parametric_polar"] = audit_parametric_polar


for _topic in ("radius_interval", "operations", "taylor_maclaurin", "binomial_series", "taylor_remainder", "euler_formula"):
    TASKS["verify_power_series_" + _topic] = _topic_task("app.power_series", topic=_topic)


def audit_power_series(**args):
    from app.power_series_checks import audit
    return audit(**args)


TASKS["audit_power_series"] = audit_power_series


def main() -> None:
    _limit_memory()
    job = json.loads(sys.stdin.read())
    try:
        value = TASKS[job["task"]](**job["args"])
        out = {"ok": True, "value": value}
    except Exception as e:
        out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    main()
