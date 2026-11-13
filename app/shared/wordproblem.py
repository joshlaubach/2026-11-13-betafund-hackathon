"""Word-problem pipeline: the model writes structure and a statement, the server derives the answer, and a second,
independent model call solves the statement blind. See docs/wordproblem_contract.md.

Two halves:
- `verify(...)` runs in the sandbox (app/worker.py). It parses the structure, checks that every given and no other
  number appears in the statement, derives the answer with SymPy by a named method, and substitutes the full
  solution back into every relation.
- `verifier(...)` builds the async pipeline verifier: it calls `verify` in the sandbox, then asks the model to
  solve the finished statement with no other input and compares its final answer with the server's.

Methods are registered with `register_method`. `solve` ships here; a topic that needs another (related rates,
optimization, work...) registers it from its own module and names that module in `method_module`.
"""
import hashlib
import importlib
import json
import re
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from string import Template
from typing import Callable

import sympy as sp

from app.shared.clean_answer import canon, value_reason
from app.shared.integral_core import L, Reject, _shape
from app.shared.integral_finish import scientific_reason
from app.safe_parse import ParseError, safe_parse

_DIR = Path(__file__).parent.parent / "llm" / "prompts"   # app/llm/prompts, one level above shared/
MAX_RELATIONS, MAX_GIVENS, MAX_STATEMENT = 6, 8, 1500
REL_TOL, ABS_TOL = 1e-3, 1e-9
_NAME = re.compile(r"[A-Za-z][0-9]?$")
_RESERVED = {"e", "E", "I"}
_NUMBER = re.compile(r"(?<![\w.^_{])\d+(?:\.\d+)?(?![\w])")
_TEXT = re.compile(r"\d+(?:\.\d+)?$")
_GREEK = set("alpha beta gamma delta epsilon zeta eta theta iota kappa lamda mu nu xi rho sigma tau phi chi psi omega".split())

FAILURE_CODES = (
    "shape", "parse", "name", "given_text", "given_missing", "unused_given", "axes",
    "method", "underdetermined", "no_solution", "not_unique", "not_finite", "answer_rule", "residual",
    "blind_unavailable", "blind_unparsed", "blind_mismatch", "blind_unit", "timeout")


@dataclass
class Ctx:
    """What a method sees: relations as `lhs - rhs` expressions, exact givens, the unknown, the recipe params."""
    relations: list[sp.Expr]
    givens: dict[sp.Symbol, sp.Rational]
    unknown: sp.Symbol
    unit: str
    params: dict[str, str]
    symbols: dict[str, sp.Symbol]


@dataclass
class Derived:
    value: sp.Expr
    steps: list[dict]
    full: dict[sp.Symbol, sp.Expr] = field(default_factory=dict)   # every solved variable, for the residual check
    raw: dict = field(default_factory=dict)
    relations: list[sp.Expr] | None = None    # the relations to substitute back into, if not ctx.relations


METHODS: dict[str, Callable[[Ctx], Derived]] = {}


def register_method(name: str):
    def deco(fn):
        if name in METHODS:
            raise ValueError(f"word-problem method {name} registered twice")
        METHODS[name] = fn
        return fn
    return deco


def fail(code: str, reason: str, cause: str = "slip") -> Reject:
    """A rejection that carries a code from FAILURE_CODES in `cap`, so scripts can count causes."""
    return Reject(cause, reason, cap=code)


def _step(text: str, latex: str, sympy_: str | None = None) -> dict:
    return {"text": text, "latex": latex, "sympy": sympy_}


@register_method("solve")
def _solve(c: Ctx) -> Derived:
    """Solve the relations for the unknown given the givens. Real solutions only; with several, positive ones
    only; the unknown must come out as exactly one value."""
    free = sorted({s for r in c.relations for s in r.free_symbols} - set(c.givens), key=str)
    if c.unknown not in free:
        raise fail("method", "the unknown does not appear in any relation")
    eqs = [r.subs(c.givens) for r in c.relations]
    sols = sp.solve(eqs, free, dict=True)
    sols = [s for s in sols if all(v.is_real is not False for v in s.values())]
    if not sols:
        raise fail("no_solution", "the relations have no real solution for the given values", "redraw")
    if any(c.unknown not in s or s[c.unknown].free_symbols for s in sols):
        raise fail("underdetermined", "the givens do not determine the unknown; add a given or a relation")
    if len({s[c.unknown] for s in sols}) > 1:
        sols = [s for s in sols if s[c.unknown].is_positive]
    values = {s[c.unknown] for s in sols}
    if len(values) != 1:
        raise fail("not_unique", "the unknown has more than one admissible value; make the situation fix one")
    sol = next(s for s in sols if s[c.unknown] in values)
    full = {k: v for k, v in sol.items() if not v.free_symbols}
    value = sol[c.unknown]
    shown = [sp.Eq(r.subs(c.givens), 0) for r in c.relations]
    steps = [
        _step("Write the relations among the quantities.", ",\\ ".join(L(sp.Eq(r, 0)) for r in c.relations)),
        _step("Substitute the given values.", ",\\ ".join(L(e) for e in shown)),
        _step(f"Solve for ${L(c.unknown)}$.", f"{L(c.unknown)} = {L(value)}", str(value)),
    ]
    return Derived(value, steps, full, {"n_unknowns": len(free)})


def _symbol(name: str, symbols: dict) -> sp.Symbol:
    if not (_NAME.match(name) or name in _GREEK) or name in _RESERVED:
        raise fail("name", f"variable name {name!r} must be one letter (optionally followed by a digit), "
                           "a Greek letter name, and not e, E or I")
    return symbols.setdefault(name, sp.Symbol(name, real=True))


def _parse(text: str, symbols: dict, label: str) -> sp.Expr:
    try:
        e = safe_parse(text, symbols)
    except ParseError as err:
        raise fail("parse", f"{label}: {err}") from None
    if not isinstance(e, sp.Expr) or e.has(sp.zoo, sp.nan, sp.oo, -sp.oo, sp.I):
        raise fail("parse", f"{label} must be a plain real expression")
    return e


def _relation(text: str, symbols: dict) -> sp.Expr:
    if text.count("=") != 1 or any(t in text for t in ("<", ">", "!")):
        raise fail("parse", f"relation {text!r} must contain exactly one '='")
    lhs, rhs = text.split("=")
    for side in (lhs, rhs):
        for name in re.findall(r"[A-Za-z]+[0-9]*", side):
            if name not in _RESERVED and (_NAME.match(name) or name in _GREEK):
                _symbol(name, symbols)
    return _parse(lhs, symbols, "relation") - _parse(rhs, symbols, "relation")


def _given_value(g: dict, symbols: dict) -> tuple[sp.Symbol, sp.Rational, str]:
    name, text = g["name"], g["text"]
    if not _TEXT.match(text):
        raise fail("given_text", f"given {name}: text must be the number as written in the statement, an integer "
                                 "or a decimal such as 12 or 2.5")
    sym = _symbol(name, symbols)
    value = _parse(g["value"], symbols, f"given {name}")
    if not value.is_number:
        raise fail("parse", f"given {name}: value must be a number")
    if sp.nsimplify(value) != sp.Rational(text):
        raise fail("given_text", f"given {name}: text {text} and value {g['value']} are different numbers")
    return sym, sp.Rational(text), text


def _statement_numbers(statement: str, texts: set[str], allowed: set[str]) -> list[str]:
    """Every given must appear in the statement. A number that is not a given (60 seconds, 100 cm per metre) is
    allowed; it is returned so the caller can record it, and the blind re-solve is what catches a wrapper that
    drifted from its structure."""
    present = {m.group() for m in _NUMBER.finditer(statement)}
    for t in sorted(texts):
        if t not in present:
            raise fail("given_missing", f"the given value {t} does not appear in the statement")
    return sorted(present - texts - allowed, key=float)


def _axes_reason(axes: dict, c: Ctx, method: str) -> str | None:
    """The server assigned the setup (method, unknown, relations the model must use, number of givens).
    Compare it with what the model wrote and name the first thing that differs."""
    if "method" in axes and axes["method"] != method:
        return f"the method must be {axes['method']}"
    if "unknown" in axes and axes["unknown"] != c.unknown.name:
        return f"the unknown must be {axes['unknown']}, not {c.unknown.name}"
    if "n_givens" in axes and int(axes["n_givens"]) != len(c.givens):
        return f"there must be exactly {axes['n_givens']} givens"
    for form in axes.get("relations", []):
        want = _relation(form, dict(c.symbols))
        if not any(sp.simplify(want - r) == 0 or sp.simplify(want + r) == 0 for r in c.relations):
            return f"a relation equivalent to {form} must appear"
    return None


def _hash(c: Ctx, method: str) -> str:
    rel = sorted(sp.srepr(sp.expand(r)) for r in c.relations)
    giv = sorted((k.name, str(v)) for k, v in c.givens.items())
    return hashlib.sha256(json.dumps([rel, giv, c.unknown.name, method]).encode()).hexdigest()[:16]


def _shape_key(c: Ctx, method: str, context: str) -> str:
    rel = sorted(_shape(sp.expand(r), False) for r in c.relations)
    return "|".join(rel) + f"|{method}|{c.unknown.name}|{context}"


def verify(structure: dict, axes: dict | None = None, calculator: str = "none", method: str = "solve",
           method_module: str | None = None) -> dict:
    try:
        return _verify(structure, axes or {}, calculator, method, method_module)
    except Reject as r:
        return {"ok": False, "cause": r.cause, "reason": r.reason, "cap": r.cap, "code": r.cap}


def _verify(s: dict, axes: dict, calculator: str, method: str, method_module: str | None) -> dict:
    statement, rels, givens, unknown = s["statement"].strip(), s["relations"], s["givens"], s["unknown"]
    if not 1 <= len(rels) <= MAX_RELATIONS or not 1 <= len(givens) <= MAX_GIVENS or not statement \
            or len(statement) > MAX_STATEMENT:
        raise fail("shape", f"need 1-{MAX_RELATIONS} relations, 1-{MAX_GIVENS} givens and a statement of "
                            f"at most {MAX_STATEMENT} characters")
    if method_module:
        if not method_module.startswith("app."):
            raise fail("method", "method modules live under app.", "redraw")
        importlib.import_module(method_module)
    if method not in METHODS:
        raise fail("method", f"unknown method {method}", "redraw")
    symbols: dict[str, sp.Symbol] = {}
    parsed = [_relation(r, symbols) for r in rels]
    parsed_givens, texts = {}, set()
    for g in givens:
        sym, val, text = _given_value(g, symbols)
        if sym in parsed_givens:
            raise fail("name", f"given {g['name']} is listed twice")
        parsed_givens[sym] = val
        texts.add(text)
    u_sym = _symbol(unknown["name"], symbols)
    if u_sym in parsed_givens:
        raise fail("name", "the unknown is also a given")
    used = {v for r in parsed for v in r.free_symbols}
    if u_sym not in used:
        raise fail("method", "the unknown does not appear in any relation")
    if idle := [k.name for k in parsed_givens if k not in used]:
        raise fail("unused_given", f"given {', '.join(idle)} appears in no relation")
    extra_numbers = _statement_numbers(
        statement, texts, set(str(axes.get("allowed_numbers", "")).replace(" ", "").split(",")) - {""})
    params = {k: str(v) for k, v in (s.get("params") or {}).items()}
    ctx = Ctx(parsed, parsed_givens, u_sym, unknown.get("unit") or "", params, symbols)
    if why := _axes_reason(axes, ctx, method):
        raise fail("axes", why, "redraw")

    d = METHODS[method](ctx)
    value = canon(d.value)
    if value.is_real is not True or value.has(sp.zoo, sp.nan, sp.oo, -sp.oo):
        raise fail("not_finite", "the answer is not a finite real number", "redraw")
    check = ctx.relations if d.relations is None else d.relations
    env = {**ctx.givens, **d.full, ctx.unknown: value}
    for r in check:
        left = sp.simplify(r.subs(env))
        if left != 0 and (left.free_symbols or abs(complex(sp.N(left, 30))) > 1e-9):
            raise fail("residual", "the derived values do not satisfy a relation", "redraw")
    if calculator == "none":
        if (why := value_reason(value, True)):
            raise fail("answer_rule", f"answer is not a short exact form ({why})", "redraw")
        shown = L(value)
    else:
        if (why := scientific_reason(value)):
            raise fail("answer_rule", f"answer is not a usable decimal ({why})", "redraw")
        shown = f"{float(sp.N(value, 15)):.3f}"
    unit = ctx.unit
    tail = (f"Give the answer to three decimal places" if calculator == "scientific" else "Give an exact answer") + (
        f" in {unit}." if unit else ".")
    num = float(sp.N(value, 15))
    answer = {"type": "numeric", "latex": shown + (f"\\ \\text{{{unit}}}" if unit else ""), "sympy": str(value),
              "numeric": num}
    steps = d.steps
    raw = {"ops_integrand": sum(int(sp.count_ops(r)) for r in ctx.relations), "ops_R": 0,
           "ops_F": int(sp.count_ops(value)), "g_polynomial": True, "deg_g": None, "n_terms_R": len(ctx.relations),
           "const_factor": False, "definite": False, "has_discontinuity": False, "steps": len(steps),
           "answer_type": "numeric", "rules": [], "method": method, "n_givens": len(ctx.givens),
           "n_relations": len(ctx.relations), "extra_numbers": extra_numbers, **d.raw}
    return {"ok": True, "statement": f"{statement} {tail}", "answer": answer, "steps": steps, "method": method,
            "calculator_check": "passed", "hash": _hash(ctx, method),
            "shape": _shape_key(ctx, method, str(axes.get("context", ""))), "has_discontinuity": False,
            "unit": unit, "value": num, "raw": raw}


def compare(server: float, blind: str, rel: float = REL_TOL, abs_tol: float = ABS_TOL) -> dict:
    """Sandbox task: parse the blind solver's final answer (never eval) and compare it with the server's."""
    try:
        v = float(sp.N(safe_parse(blind), 15))
    except (ParseError, TypeError, ValueError):
        return {"ok": False, "code": "blind_unparsed", "reason": "the blind answer could not be read as a number"}
    err = abs(v - server)
    return {"ok": err <= max(abs_tol, rel * abs(server)), "blind": v, "error": err,
            "code": "blind_mismatch", "reason": f"the blind answer {v:g} differs from the derived {server:g}"}


def _unit_key(u: str) -> str:
    u = u.lower().replace("³", "^3").replace("²", "^2").replace(" per ", "/").replace("\\,", "")
    return re.sub(r"[\s.*]|\\text|[{}]", "", u).replace("**", "^")


@cache
def _blind_file(suffix: str) -> str:
    return (_DIR / f"wordproblem_blind.{suffix}").read_text(encoding="utf-8")


async def blind_solve(statement: str, level: int, calculator: str):
    """One model call with the statement alone. Returns (raw text, parsed reply or None, usage)."""
    from app.llm import client as llm        # lazy: the sandbox half of this module must start fast
    system = Template(_blind_file("md")).safe_substitute(calculator=calculator)
    done = await llm.complete(llm.model_for(level), system, [{"role": "user", "content": statement}],
                              json.loads(_blind_file("schema.json")))
    reply = None
    if done.text is not None:
        try:
            reply = json.loads(done.text)
        except json.JSONDecodeError:
            reply = None
    ok = isinstance(reply, dict) and isinstance(reply.get("answer"), str) and isinstance(reply.get("unit"), str)
    return done.text, reply if ok else None, done.usage


def _fields_ok(p: dict) -> bool:
    str_list = lambda v: isinstance(v, list) and all(isinstance(i, str) for i in v)
    giv = p.get("givens")
    unk = p.get("unknown")
    return (isinstance(p.get("statement"), str) and str_list(p.get("relations")) and isinstance(giv, list)
            and all(isinstance(g, dict) and all(isinstance(g.get(k), str) for k in ("name", "value", "text"))
                    for g in giv)
            and isinstance(unk, dict) and isinstance(unk.get("name"), str))


def _params(p: dict) -> dict:
    """The optional `params` field arrives as a list of {key, value} pairs (JSON-schema friendly) or an object."""
    raw = p.get("params") or []
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    return {str(i["key"]): str(i["value"]) for i in raw if isinstance(i, dict) and "key" in i and "value" in i}


def verifier(label: str, *, method: str = "solve", method_module: str | None = None, blind: bool = True):
    """The pipeline verifier for a word-problem topic. Register it with
    `register("calc.<name>")(wordproblem.verifier("<name>", ...))`."""
    async def run(cand, topic, calculator):
        from app import sandbox
        from app.verify import VerifyResult
        p = cand.payload
        if not _fields_ok(p):
            return VerifyResult(False, label, "reply must have statement, relations (strings), givens "
                                "({name, value, text} strings) and unknown ({name, unit})", cause="slip")
        structure = {"statement": p["statement"], "relations": p["relations"], "givens": p["givens"],
                     "unknown": p["unknown"], "params": _params(p)}
        axes = {"recipe": cand.recipe["id"], **cand.recipe["axes"]} if "axes" in cand.recipe else None
        args = {"structure": structure, "axes": axes, "calculator": calculator.value, "method": method,
                "method_module": method_module}
        try:
            r = await sandbox.run("wordproblem_verify", args)
        except sandbox.SandboxTimeout:
            return VerifyResult(False, label, "verification timed out", cause="redraw", timed_out=True)
        except sandbox.SandboxError as e:
            return VerifyResult(False, label, f"verifier error: {e}", cause="redraw")
        v = r.value
        if not v["ok"]:
            return VerifyResult(False, label, v["reason"], cause=v["cause"], elapsed_ms=r.elapsed_ms)
        if not blind or cand.raw is None:        # the offline samplers write the statement from a template
            return VerifyResult(True, v["method"], elapsed_ms=r.elapsed_ms, derived=v)
        return await _blind_check(cand, v, label, calculator.value, r.elapsed_ms)
    return run


async def _blind_check(cand, v: dict, label: str, calculator: str, elapsed_ms: int):
    from app import sandbox
    from app.llm.client import Usage
    from app.verify import ExtraCall, VerifyResult
    extra: list[ExtraCall] = []
    try:
        text, reply, usage = await blind_solve(v["statement"], cand.level, calculator)
    except Exception as e:
        extra.append(ExtraCall("blind_solve", None, Usage(), "invalid",
                               f"blind_unavailable: model call failed: {type(e).__name__}"))
        return VerifyResult(False, label, "the independent solve could not run", cause="redraw",
                            elapsed_ms=elapsed_ms, extra=extra)
    if reply is None:
        extra.append(ExtraCall("blind_solve", text, usage, "invalid",
                               "blind_unavailable: reply was refused, cut off or not valid"))
        return VerifyResult(False, label, "the independent solve returned no usable answer", cause="redraw",
                            elapsed_ms=elapsed_ms, extra=extra)
    try:
        c = (await sandbox.run("wordproblem_compare", {"server": v["value"], "blind": reply["answer"]})).value
    except (sandbox.SandboxTimeout, sandbox.SandboxError):
        c = {"ok": False, "code": "blind_unparsed", "reason": "the blind answer could not be read as a number"}
    unit_ok = not v["unit"] or not reply["unit"] or _unit_key(v["unit"]) == _unit_key(reply["unit"])
    if c["ok"] and unit_ok:
        extra.append(ExtraCall("blind_solve", text, usage, "passed", None))
        return VerifyResult(True, v["method"] + "+blind", elapsed_ms=elapsed_ms, derived=v, extra=extra)
    code, why = (c["code"], c["reason"]) if not c["ok"] else (
        "blind_unit", f"the independent solver answered in {reply['unit']}, not {v['unit']}")
    extra.append(ExtraCall("blind_solve", text, usage, "failed", f"{code}: {why}"))
    note = ("An independent solver reading only the statement disagrees: " + why +
            ". Make the statement unambiguous, or fix the relations, givens or unknown.")
    return VerifyResult(False, label, note, cause="slip" if not cand.repaired else "redraw",
                        elapsed_ms=elapsed_ms, extra=extra)
