"""The offline engine: a verified problem for a topic at any level and calculator tier with no model call.

Each topic that has a sampler is registered here. A sampler takes a recipe, the axes the server assigned to it,
the answer types wanted, the calculator tier and a seed, and returns the reply a good model would have given
({"payload", "result"}) or None. Its payload goes through the same verifier as a model reply, so what the offline
engine returns is checked exactly like the model's output.

u-substitution has no sampler (its recipes depend on the model's choice of g and R), so it is LLM-only.
"""
from functools import partial

from app.calc1 import applications_b_samples, rates_optimization_samples, applications_samples, derivative_advanced_samples, derivative_rules_samples, derivatives_samples, limits_samples
from app.calc2 import by_parts_samples, improper_samples, partial_samples, rules_samples, strategy_samples, trig_samples, trig_sub_samples

SAMPLERS = {
    "by_parts": by_parts_samples.generate,
    "trig_integrals": partial(trig_samples.generate, hyp=False),
    "hyperbolic": partial(trig_samples.generate, hyp=True),
    "partial_fractions": partial_samples.generate,
    "trig_substitution": trig_sub_samples.generate,
    "improper": improper_samples.generate,
    "strategy": strategy_samples.generate,
    "rules": rules_samples.generate,
    "error_bounds": rules_samples.generate_bounds,
    **{stem: partial(limits_samples.generate, stem) for stem in limits_samples.TABLES},   # limits and continuity
    **{stem: partial(derivatives_samples.generate, stem) for stem in derivatives_samples.TABLES},   # derivatives
    **{stem: partial(derivative_rules_samples.generate, stem) for stem in derivative_rules_samples.TABLES},
    **{stem: partial(derivative_advanced_samples.generate, stem) for stem in derivative_advanced_samples.TABLES},
    **{stem: partial(applications_samples.generate, stem) for stem in applications_samples.TABLES},
    **{stem: partial(applications_b_samples.generate, stem) for stem in applications_b_samples.TABLES},
    **{stem: partial(rates_optimization_samples.generate, stem) for stem in rates_optimization_samples.TABLES},
}


def supports(stem: str) -> bool:
    return stem in SAMPLERS


def payload_for_reply(stem: str, payload: dict) -> dict:
    """The sampler's payload in the shape of the model's JSON reply (the verifier reads that shape)."""
    out = dict(payload)
    if stem == "rules":
        out["values"] = out.pop("extra", None)
    elif stem == "error_bounds":
        out["eps"] = out.pop("extra", None)
    return out


from app.calc1 import integration_basics_samples
from app.calc1.integration_basics import TOPICS as _BASICS_TOPICS
for _topic in _BASICS_TOPICS:
    SAMPLERS[_topic] = partial(integration_basics_samples.generate, topic=_topic)


from app.calc2 import sequences_series_samples
from app.calc2.sequences_series import TOPICS as _SEQUENCES_SERIES_TOPICS
for _topic in _SEQUENCES_SERIES_TOPICS:
    SAMPLERS[_topic] = partial(sequences_series_samples.generate, topic=_topic)


from app.calc1 import integral_applications_samples
from app.calc1.integral_applications import TOPICS as _INTEGRAL_APPLICATION_TOPICS
for _topic in _INTEGRAL_APPLICATION_TOPICS:
    SAMPLERS[_topic] = partial(integral_applications_samples.generate, topic=_topic)

from app.calc2 import arc_length_samples
SAMPLERS["arc_length"] = arc_length_samples.generate


from app.calc2 import series_tests_samples
from app.calc2.series_tests import TOPICS as _SERIES_TESTS_TOPICS
for _topic in _SERIES_TESTS_TOPICS:
    SAMPLERS[_topic] = partial(series_tests_samples.generate, topic=_topic)


from app.calc2 import power_series_samples
from app.calc2.power_series import TOPICS as _POWER_SERIES_TOPICS
for _topic in _POWER_SERIES_TOPICS:
    SAMPLERS[_topic] = partial(power_series_samples.generate, topic=_topic)

from app.calc2 import parametric_polar_samples
from app.calc2.parametric_polar import TOPICS as _PARAMETRIC_POLAR_TOPICS
for _topic in _PARAMETRIC_POLAR_TOPICS:
    SAMPLERS[_topic] = partial(parametric_polar_samples.generate, topic=_topic)
