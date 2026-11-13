"""Offline structures for Cartesian arc length."""
from app.calc2 import arc_length


def generate(recipe, axes, answers, calculator="none", seed=0):
    payload = {k: str(v) for k, v in axes.items()}
    result = arc_length.verify(**payload, axes={"recipe": recipe["id"], **axes}, calculator=calculator)
    return {"payload": payload, "result": result} if result["ok"] and result["answer"]["type"] in answers else None
