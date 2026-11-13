import asyncio
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import catalog, pipeline, sandbox
from app.auth import COOKIE, check_limits, lookup, require_key
from app.config import settings
from app.db import ApiKey, SessionLocal, get_session, init_db
from app.schemas import Course, GenerateRequest, GenerateResponse, public_dump, public_problem

templates = Jinja2Templates(Path(__file__).parent / "templates")


@asynccontextmanager
async def lifespan(_):
    init_db()
    catalog.get()  # fail fast on a bad catalog
    yield


app = FastAPI(title="Verified Math Problem Generator", lifespan=lifespan)


# ---------- API

@app.get("/v1/catalog")
def get_catalog():
    cat = catalog.get()
    return {"courses": [
        {"slug": c.value, "title": catalog.COURSE_TITLES[c], "topics": [
            {"id": t.id, "title": t.title, "status": t.status,
             "calculator_levels": t.calculator_levels, "answer_types": t.answer_types,
             "figures": t.figures, "descriptors": t.descriptors_for(c),
             "levels": sorted(pipeline.offered_levels(t) or range(1, 6))}
            for t in cat.for_course(c)]}
        for c in Course]}


def _prepare(req: GenerateRequest, key: ApiKey, s: Session):
    topics = pipeline.validate(req)
    check_limits(s, key, req.count)
    return topics


@app.post("/v1/generate")
async def generate(req: GenerateRequest, key: ApiKey = Depends(require_key),
                   s: Session = Depends(get_session)):
    topics = _prepare(req, key, s)
    final = None
    async for item in pipeline.run(req, topics, key, s):
        final = item
    status = 200 if final.problems else 502
    return JSONResponse(public_dump(final, settings.include_debug), status_code=status)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@app.post("/v1/generate/stream")
async def generate_stream(req: GenerateRequest, key: ApiKey = Depends(require_key),
                          s: Session = Depends(get_session)):
    topics = _prepare(req, key, s)

    async def events():
        # Own session: request-scoped dependencies may close before the body streams.
        try:
            with SessionLocal() as s2:
                async for item in pipeline.run(req, topics, key, s2):
                    if isinstance(item, GenerateResponse):
                        data = public_dump(item, settings.include_debug)
                        yield _sse("done", {k: data[k] for k in ("generation_id", "shortfall", "meta")})
                    else:
                        yield _sse("problem", public_problem(item, settings.include_debug))
        except Exception:
            yield _sse("error", {"message": "generation failed"})
            raise

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/health")
def health():
    return {"ok": True}


# ---------- Deployment probe (enabled with PROBE_ENABLED=true; remove after Phase 1)

def _probe_guard():
    if os.environ.get("PROBE_ENABLED", "").lower() != "true":
        raise HTTPException(404)


@app.get("/probe", dependencies=[Depends(_probe_guard)])
async def probe():
    out = {}
    r = await sandbox.run("parse", {"expr": "x^2 + sin(3x)"})
    out["parse"] = {"value": r.value["str"], "ms": r.elapsed_ms}
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    try:
        await sandbox.run("spin", {}, timeout=3)
        out["kill"] = {"ok": False, "detail": "spin returned"}
    except sandbox.SandboxTimeout:
        out["kill"] = {"ok": True, "ms": int((loop.time() - t0) * 1000)}
    r = await sandbox.run("parse", {"expr": "1+1"})
    out["after_kill"] = {"value": r.value["str"], "ms": r.elapsed_ms}
    return out


@app.get("/probe/stream", dependencies=[Depends(_probe_guard)])
async def probe_stream():
    async def ticks():
        loop = asyncio.get_running_loop()
        t0 = loop.time()
        for i in range(5):
            yield _sse("tick", {"i": i, "t": round(loop.time() - t0, 2)})
            await asyncio.sleep(1)
        yield _sse("done", {})
    return StreamingResponse(ticks(), media_type="text/event-stream")


# ---------- HTML

@app.get("/", response_class=HTMLResponse)
def index(request: Request, s: Session = Depends(get_session)):
    if lookup(s, request.cookies.get(COOKIE)) is None:
        return RedirectResponse("/login", 303)
    courses = [(c.value, catalog.COURSE_TITLES[c]) for c in Course]
    return templates.TemplateResponse(request, "index.html", {"courses": courses})


@app.get("/ui/topics", response_class=HTMLResponse)
def topic_options(request: Request, course: Course):
    return templates.TemplateResponse(request, "_topics.html",
                                      {"topics": catalog.get().for_course(course)})


def _notice(request: Request, message: str, signin: bool = False):
    """A message in place of results. Status 200 so HTMX swaps it in (it ignores 4xx bodies by default)."""
    return templates.TemplateResponse(request, "_notice.html", {"message": message, "signin": signin})


@app.post("/ui/generate", response_class=HTMLResponse)
async def ui_generate(request: Request, course: Course = Form(...), topic_ids: list[str] = Form(default=[]),
                      difficulty: int = Form(...), calculator: str = Form("none"), count: int = Form(...),
                      offline: str | None = Form(None), s: Session = Depends(get_session)):
    """The form's Generate button: the same pipeline, key and quota checks as /v1/generate, rendered as HTML."""
    key = lookup(s, request.cookies.get(COOKIE))
    if key is None:
        return _notice(request, "Your session has expired.", signin=True)
    try:
        req = GenerateRequest(course=course, topic_ids=topic_ids, difficulty=difficulty, calculator=calculator,
                              count=count, options={"figure_format": "svg", "engine": "offline" if offline else None})
        topics = _prepare(req, key, s)
    except ValidationError as e:
        return _notice(request, "Check the form: " + "; ".join(err["msg"] for err in e.errors()))
    except HTTPException as e:
        return _notice(request, str(e.detail))
    final = None
    async for item in pipeline.run(req, topics, key, s):
        final = item
    return templates.TemplateResponse(request, "_results.html", {
        "resp": final, "titles": {t.id: t.title for t in topics}})


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login", response_class=HTMLResponse)
def login(request: Request, code: str = Form(...), s: Session = Depends(get_session)):
    code = code.strip()
    if lookup(s, code) is None:
        return templates.TemplateResponse(request, "login.html",
                                          {"error": "That invite code isn't valid."}, status_code=401)
    resp = RedirectResponse("/", 303)
    resp.set_cookie(COOKIE, code, httponly=True, samesite="lax", secure="https" in (request.url.scheme, request.headers.get("x-forwarded-proto")),
                    max_age=60 * 60 * 24 * 90)
    return resp
