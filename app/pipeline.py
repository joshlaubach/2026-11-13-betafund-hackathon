"""Request orchestration: validate against the catalog, then run one slot per requested
problem. A slot draws a recipe, asks the model for a candidate, verifies it in the
sandbox, and either repairs it (model slip), redraws (bad luck), or gives up after
MAX_ATTEMPTS. Every attempt is logged to the attempt table."""
import asyncio
import random
import secrets
import time
from dataclasses import dataclass, field
from typing import AsyncIterator

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import catalog, difficulty, verify
from app.config import settings
from app.db import ApiKey, Attempt, Generation
from app.llm.client import Usage
from app.schemas import (Answer, AnswerType, DifficultyFeatures, Figure, GenerateRequest, GenerateResponse,
                         Meta, Problem, Shortfall, Step, Verification)
from app.strategies import REGISTRY as STRATEGIES, Allocation, Spec
from app.strategies import llm_backward, offline as offline_strategy  # noqa: F401  (register the strategies)
from app import offline as offline_engine
from app.strategies.llm_backward import offered_levels
from app.verify import calc  # noqa: F401  (registers the verifiers)

MAX_ATTEMPTS = 3
call_hook = None         # set by the pass-rate harness to receive one dict per model call


def _strategy_name(topic, req: GenerateRequest) -> str:
    """The generation strategy for this topic: the model's (the catalog's) or the offline samplers."""
    engine = req.options.engine or settings.engine
    return "offline" if engine == "offline" else topic.strategy


def validate(req: GenerateRequest) -> list[catalog.Topic]:
    cat = catalog.get()
    topics, errors = [], []
    for tid in dict.fromkeys(req.topic_ids):
        t = cat.topics.get(tid)
        if t is None:
            errors.append(f"unknown topic {tid}")
        elif req.course not in t.courses:
            errors.append(f"{tid} is not part of {req.course.value}")
        elif t.status != "implemented":
            errors.append(f"{tid} is not available yet")
        elif req.calculator not in t.calculator_levels:
            errors.append(f"{tid} does not support calculator={req.calculator.value}")
        elif req.options.answer_types and not set(req.options.answer_types) & set(t.answer_types):
            errors.append(f"{tid} has none of the requested answer types")
        elif (req.options.engine or settings.engine) == "offline" and not offline_engine.supports(catalog.stem_of(tid)):
            errors.append(f"{tid} has no offline engine; use engine=llm")
        elif (off := offered_levels(t)) is not None and not off & set(range(req.level_range[0], req.level_range[1] + 1)):
            errors.append(f"{tid} has no problems at difficulty {req.level_range[0]}"
                          + (f" to {req.level_range[1]}" if req.level_range[1] != req.level_range[0] else "")
                          + f"; it offers levels {sorted(off)}")
        else:
            topics.append(t)
    if errors:
        raise HTTPException(422, errors)
    return topics


@dataclass
class _Run:
    req: GenerateRequest
    deadline: float
    sem: asyncio.Semaphore
    warm: asyncio.Event            # set once the first call has primed the prompt cache
    seen_hashes: set
    seen_shapes: set = field(default_factory=set)
    taken: list[str] = field(default_factory=list)   # descriptions shown to the model
    attempts: list[Attempt] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    timed_out: bool = False
    gave_up: bool = False
    gen_id: str = ""
    alloc: Allocation | None = None


def _row(topic, strategy, level, cand=None, status="failed", reason=None, res=None, features=None) -> Attempt:
    u = cand.usage if cand else Usage()
    return Attempt(
        topic_id=topic.id, strategy=strategy.name, raw_output=cand.raw if cand else None, status=status,
        method=res.method if res and res.passed else None, failure_reason=reason,
        repair_attempt=int(bool(cand and cand.repaired)), verify_ms=res.elapsed_ms if res else None,
        difficulty_features=features or (_recipe_log(cand.recipe) if cand else None),
        assigned_level=level, input_tokens=u.input_tokens,
        output_tokens=u.output_tokens, cost_usd=u.cost_usd)


def _recipe_log(recipe: dict) -> dict:
    axes = {"axes": recipe["axes"]} if "axes" in recipe else {}
    return {"recipe": recipe["id"], "recipe_levels": recipe["levels"], **axes}


def _describe(payload: dict) -> str:
    b = payload.get("bounds")
    bounds = f", from {b.get('lower')} to {b.get('upper')}" if isinstance(b, dict) else ""
    if "g" in payload and "R" in payload:                      # u-substitution
        return f"g = {payload.get('g')}, R = {payload.get('R')}{bounds}"
    shown = ", ".join(f"{k} = {v}" for k, v in payload.items() if k != "bounds" and v not in (None, ""))
    return shown + bounds


async def _model_call(st: _Run, i: int, strategy, topic, spec: Spec, prev, reason, attempt: int = 1):
    """Slot 0's first call goes alone so the others read the cached system prompt."""
    t0 = t1 = time.perf_counter()
    if i != 0 and not st.warm.is_set():
        await st.warm.wait()
    async with st.sem:
        t1 = time.perf_counter()
        try:
            if prev is not None and reason:
                return await strategy.repair(topic, spec, prev, reason)
            return await strategy.generate(topic, spec)
        finally:
            if i == 0:
                st.warm.set()
            if call_hook:
                call_hook({"gen_id": st.gen_id, "slot": i, "attempt": attempt, "level": spec.level, "kind": "call",
                           "repair": bool(prev is not None and reason),
                           "wait_ms": int((t1 - t0) * 1000), "call_ms": int((time.perf_counter() - t1) * 1000)})


def _figure(d: dict, fmt: str) -> Figure | None:
    """The figure a verifier drew (app/figures.py), in the format the request asked for."""
    fig = d.get("figure")
    if not fig:
        return None
    return Figure(format=fmt, alt=fig["alt"], content=fig["svg"] if fmt in ("svg", "both") else None,
                  spec=fig["spec"] if fmt in ("spec", "both") else None)


def _problem(topic, req: GenerateRequest, level: int, attempt: int, res, features: dict) -> Problem:
    d, a = res.derived, res.derived["answer"]
    steps = [Step(n=n, text=s["text"], latex=s["latex"], sympy=s["sympy"], verified=True)
             for n, s in enumerate(d["steps"], 1)] if req.options.include_steps else []
    return Problem(
        id="prob_" + secrets.token_hex(6), hash=d["hash"], topic_id=topic.id, difficulty=level,
        calculator=req.calculator, statement=d["statement"],
        answer=Answer(type=AnswerType(a["type"]), latex=a["latex"], sympy=a["sympy"], numeric=a["numeric"]),
        steps=steps, requires_figure=bool(d.get("requires_figure")), figure=_figure(d, req.options.figure_format),
        difficulty_features=DifficultyFeatures(**features),
        verification=Verification(status="passed", method=res.method, attempts=attempt,
                                  calculator_check=d["calculator_check"]))


def _allowed(req: GenerateRequest, topic) -> set[str]:
    wanted = {a.value for a in req.options.answer_types} if req.options.answer_types else None
    return {a.value for a in topic.answer_types} & (wanted or {a.value for a in topic.answer_types})


async def _slot(st: _Run, i: int, topic, spec: Spec) -> Problem | None:
    strategy, verifier = STRATEGIES[_strategy_name(topic, st.req)], verify.REGISTRY[topic.verifier]
    level, allowed = spec.level, _allowed(st.req, topic)
    cand, reason = None, None            # a candidate plus a reason means: ask the model to repair it
    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            remaining = st.deadline - time.perf_counter()
            if remaining <= 0:
                st.timed_out = True
                return None
            try:
                async with asyncio.timeout(remaining):
                    cand = await _model_call(st, i, strategy, topic, spec, cand, reason, attempt)
            except TimeoutError:
                st.timed_out = True
                st.attempts.append(_row(topic, strategy, level, status="timeout",
                                        reason="request time budget exhausted"))
                return None
            except Exception as e:
                st.attempts.append(_row(topic, strategy, level, status="invalid",
                                        reason=f"model call failed: {type(e).__name__}"))
                cand, reason = None, None
                continue
            st.usage.add(cand.usage)
            if cand.payload is not None:
                st.taken.append(_describe(cand.payload))
            if cand.payload is None:
                st.attempts.append(_row(topic, strategy, level, cand, "invalid",
                                        "model reply was refused, cut off or not JSON"))
                spec.avoid_recipes.add(cand.recipe["id"])
                cand, reason = None, None
                continue

            t_verify = time.perf_counter()
            res = await verifier(cand, topic, st.req.calculator)
            if call_hook:
                ran = res.elapsed_ms or 0
                call_hook({"gen_id": st.gen_id, "slot": i, "attempt": attempt, "level": level, "kind": "verify",
                           "repair": False, "wait_ms": max(0, int((time.perf_counter() - t_verify) * 1000) - ran),
                           "call_ms": ran})
            for e in res.extra:                        # further model calls the verifier made (blind re-solve)
                st.usage.add(e.usage)
                st.attempts.append(Attempt(
                    topic_id=topic.id, strategy=e.role, raw_output=e.raw, status=e.status, failure_reason=e.reason,
                    assigned_level=level, input_tokens=e.usage.input_tokens, output_tokens=e.usage.output_tokens,
                    cost_usd=e.usage.cost_usd))
            cause, fail, features, problem = res.cause, res.reason, None, None
            if res.passed:
                d = res.derived
                if d["answer"]["type"] not in allowed:
                    cause, fail = "redraw", "answer type was not requested"
                elif d["hash"] in st.seen_hashes or d["shape"] in st.seen_shapes:
                    cause, fail = "redraw", "duplicate"
                else:
                    st.seen_hashes.add(d["hash"])
                    st.seen_shapes.add(d["shape"])
                    raw = {**d["raw"], **_recipe_log(cand.recipe)}
                    features = difficulty.features(raw, topic.difficulty.weights,
                                                   topic.difficulty.bins.get(st.req.course))
                    problem = _problem(topic, st.req, level, attempt, res, features)
            status = "passed" if problem else "timeout" if res.timed_out else "failed"
            st.attempts.append(_row(topic, strategy, level, cand, status,
                                    None if problem else f"{cause}: {fail}", res, features))
            if problem:
                return problem
            if cause == "slip" and not cand.repaired:
                reason = fail                          # one follow-up call that shows the error
                continue
            spec.avoid_recipes.add(cand.recipe["id"])
            cand, reason = None, None                  # redraw with a fresh recipe
        st.gave_up = True
        return None
    finally:
        if i == 0:
            st.warm.set()


async def run(req: GenerateRequest, topics: list[catalog.Topic], key: ApiKey,
              s: Session) -> AsyncIterator[Problem | GenerateResponse]:
    """Yield each verified Problem as it passes, then the final GenerateResponse."""
    t0 = time.perf_counter()
    gen_id = "gen_" + secrets.token_hex(6)
    rng = random.Random(req.options.seed if req.options.seed is not None else secrets.randbits(64))
    lo, hi = req.level_range
    st = _Run(req, t0 + settings.request_budget_s, asyncio.Semaphore(settings.llm_concurrency),
              asyncio.Event(), set(req.options.exclude_hashes), gen_id=gen_id)
    slots = []
    for i in range(req.count):
        topic, level = topics[i % len(topics)], rng.randint(lo, hi)
        if (off := offered_levels(topic)) is not None and level not in off:
            level = rng.choice(sorted(off & set(range(lo, hi + 1))))   # validate() guarantees one exists
        slots.append((topic, level, random.Random(rng.getrandbits(64))))
    st.alloc = Allocation(random.Random(rng.getrandbits(64)))
    specs = []
    for topic, level, slot_rng in slots:                 # every slot gets its recipe before any call starts
        spec = Spec(req.course, level, req.calculator, _allowed(req, topic), slot_rng, taken=st.taken, alloc=st.alloc)
        if plan := getattr(STRATEGIES[_strategy_name(topic, req)], "plan", None):
            plan(topic, spec)
        specs.append(spec)
    tasks = [asyncio.create_task(_slot(st, i, slots[i][0], specs[i])) for i in range(len(slots))]
    problems: list[Problem] = []
    try:
        for fut in asyncio.as_completed(tasks):
            if problem := await fut:
                problems.append(problem)
                yield problem
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        shortfall = None
        if len(problems) < req.count:
            reason = ("timeout" if st.timed_out else "verification_failed" if not problems
                      else "retry_cap_reached")
            shortfall = Shortfall(requested=req.count, returned=len(problems), reason=reason)
        u = st.usage
        meta = Meta(model=u.model, input_tokens=u.input_tokens, output_tokens=u.output_tokens,
                    latency_ms=int((time.perf_counter() - t0) * 1000), cost_usd=round(u.cost_usd, 6))
        s.add(Generation(
            id=gen_id, key_id=key.id, request=req.model_dump(mode="json"), course=req.course.value,
            topic_ids=[t.id for t in topics], requested=req.count, returned=len(problems),
            shortfall_reason=shortfall and shortfall.reason, model=meta.model,
            input_tokens=meta.input_tokens, output_tokens=meta.output_tokens,
            cost_usd=meta.cost_usd, latency_ms=meta.latency_ms))
        s.flush()
        for a in st.attempts:
            a.generation_id = gen_id
        s.add_all(st.attempts)
        s.commit()
    yield GenerateResponse(generation_id=gen_id, request=req, problems=problems,
                           shortfall=shortfall, meta=meta)
