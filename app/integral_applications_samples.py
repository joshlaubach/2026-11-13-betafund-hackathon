"""Offline structures for area and volume applications."""
from app import integral_applications


def generate(recipe, axes, answers, calculator="none", seed=0, topic=None):
    payload = {k: str(v) for k, v in axes.items()}
    result = integral_applications.verify(topic, axes={"recipe": recipe["id"], **axes},
                                          calculator=calculator, **payload)
    return {"payload": payload, "result": result} if result["ok"] and result["answer"]["type"] in answers else None
