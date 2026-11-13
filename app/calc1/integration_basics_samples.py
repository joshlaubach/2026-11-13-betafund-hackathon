"""Seeded offline replies for the integration-basics chapter."""
from app.calc1 import integration_basics


def generate(recipe, axes, answers, calculator="none", seed=0, topic=None):
    payload = {k: str(v) for k, v in axes.items() if k not in ("lower", "upper")}
    payload["bounds"] = ({"lower": str(axes["lower"]), "upper": str(axes["upper"])}
                         if "lower" in axes else None)
    # Assigned formulas set the structure; scale only where the recipe permits it.
    if "f" not in payload:
        return None
    b = payload["bounds"]
    result = integration_basics.verify(topic, bounds=[b["lower"], b["upper"]] if b else None,
                                      axes={"recipe": recipe["id"], **axes}, calculator=calculator,
                                      **{k: v for k, v in payload.items() if k != "bounds"})
    return {"payload": payload, "result": result} if result["ok"] and result["answer"]["type"] in answers else None
