"""The FastAPI app the chat page calls. It wraps core/entry, core/photo_reader and core/bank_fallback.

Routes: GET /api/health, GET /api/topics, POST /api/read-photo, POST /api/problems,
POST /api/worksheet/read, /grade, /regrade, /profile, /clarify, /ask (server/worksheet_api.py),
POST /api/practice/steps and /api/practice/check (server/practice_api.py, core/practice.py),
POST /api/tutor/chat (server/tutor_api.py, core/tutor.py).
Nothing here echoes environment variables, tracebacks, or the API key. Unexpected
errors return HTTP 500 {"error": "internal error"} and are logged by type and message.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Literal, Optional

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from core import bank_fallback, practice
from core.entry import request_problems
from core.photo_reader import TOO_LARGE_MESSAGE
from server import photo_api, practice_api, tutor_api, worksheet_api
from server.guard import LocalGuard
from server.topics import topic_tree

logger = logging.getLogger(__name__)

BUILD_DIR: Path = bank_fallback.BUILD_DIR
ENV_API_KEY = "ANTHROPIC_API_KEY"
ENV_MODE = "ECHO_MODE"
DEFAULT_MODE = "replay"
PROBLEM_MODES = ("live", "replay", "fake", "bank")
PHOTO_MODES = ("live", "replay", "fake")
CORS_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")
CORS_METHODS = ("GET", "POST")
CORS_HEADERS = ("Content-Type",)
INTERNAL_ERROR_BODY = {"error": "internal error"}


class ProblemRequest(BaseModel):
    """Topic, level and count pass through to request_problems, which returns error statuses for bad values."""

    topic: Any
    level: Any
    # Any, not int, so a bad count reaches request_problems and returns its error status, as topic and level do.
    count: Any = None
    mode: Optional[Literal["live", "replay", "fake", "bank"]] = None


def _default_mode() -> str:
    configured = os.environ.get(ENV_MODE, DEFAULT_MODE)
    return configured if configured in PROBLEM_MODES else DEFAULT_MODE


def _internal_error(route: str, error: Exception) -> JSONResponse:
    logger.error("%s failed: %s: %s", route, type(error).__name__, error)
    return JSONResponse(status_code=500, content=dict(INTERNAL_ERROR_BODY))


def _too_large() -> JSONResponse:
    return JSONResponse(status_code=413, content={"error": TOO_LARGE_MESSAGE})


def create_app() -> FastAPI:
    app = FastAPI(title="Echo API")
    app.add_middleware(LocalGuard, allowed_origins=CORS_ORIGINS)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(CORS_ORIGINS),
        allow_methods=list(CORS_METHODS),
        allow_headers=list(CORS_HEADERS),
    )

    @app.get("/api/health", response_model=None)
    def health() -> Any:
        try:
            return {
                "ok": True,
                "live_available": bool(os.environ.get(ENV_API_KEY, "").strip()),
                "default_mode": _default_mode(),
                "echo_checked_topics": sorted(bank_fallback.echo_checked_topics(BUILD_DIR)),
                "coverage": bank_fallback.describe_coverage(BUILD_DIR),
            }
        except Exception as error:
            return _internal_error("health", error)

    @app.get("/api/topics", response_model=None)
    def topics() -> Any:
        try:
            return {"courses": topic_tree(BUILD_DIR)}
        except Exception as error:
            return _internal_error("topics", error)

    @app.post("/api/read-photo", response_model=None)
    async def read_photo_route(
        file: UploadFile = File(...),
        mode: Literal["live", "replay", "fake"] = Form(DEFAULT_MODE),
    ) -> Any:
        try:
            return await photo_api.read_uploaded_photo(file, mode)
        except photo_api.UploadTooLarge:
            return _too_large()
        except Exception as error:
            return _internal_error("read-photo", error)

    @app.post("/api/problems", response_model=None)
    def problems(body: ProblemRequest) -> Any:
        mode = body.mode or _default_mode()
        # count is passed only when the client sends one, so request_problems keeps its default of 3.
        extra = {} if body.count is None else {"count": body.count}
        try:
            return request_problems(body.topic, body.level, mode=mode, build_dir=BUILD_DIR, **extra)
        except Exception as error:
            return _internal_error("problems", error)

    @app.post("/api/worksheet/read", response_model=None)
    async def worksheet_read_route(
        file: UploadFile = File(...),
        mode: Literal["live", "replay", "fake"] = Form(DEFAULT_MODE),
    ) -> Any:
        try:
            return await worksheet_api.read_uploaded_worksheet(file, mode)
        except photo_api.UploadTooLarge:
            return _too_large()
        except Exception as error:
            return _internal_error("worksheet-read", error)

    @app.post("/api/worksheet/grade", response_model=None)
    def worksheet_grade_route(body: worksheet_api.GradeRequest) -> Any:
        try:
            return worksheet_api.grade_reading(body, BUILD_DIR)
        except Exception as error:
            return _internal_error("worksheet-grade", error)

    @app.post("/api/worksheet/regrade", response_model=None)
    def worksheet_regrade_route(body: worksheet_api.RegradeRequest) -> Any:
        try:
            return worksheet_api.regrade_graded(body)
        except Exception as error:
            return _internal_error("worksheet-regrade", error)

    @app.post("/api/worksheet/profile", response_model=None)
    def worksheet_profile_route(body: worksheet_api.ProfileRequest) -> Any:
        try:
            return worksheet_api.profile_graded(body, BUILD_DIR)
        except Exception as error:
            return _internal_error("worksheet-profile", error)

    @app.post("/api/worksheet/clarify", response_model=None)
    def worksheet_clarify_route(body: worksheet_api.ClarifyRequest) -> Any:
        try:
            return worksheet_api.clarify_text(body)
        except Exception as error:
            return _internal_error("worksheet-clarify", error)

    @app.post("/api/worksheet/ask", response_model=None)
    def worksheet_ask_route(body: worksheet_api.AskRequest) -> Any:
        try:
            return worksheet_api.ask_row(body)
        except Exception as error:
            return _internal_error("worksheet-ask", error)

    @app.post("/api/practice/steps", response_model=None)
    def practice_steps_route(body: practice_api.StepsRequest) -> Any:
        try:
            return practice.get_steps(body.topic, body.problem_id)
        except Exception as error:
            return _internal_error("practice-steps", error)

    @app.post("/api/practice/check", response_model=None)
    def practice_check_route(body: practice_api.CheckRequest) -> Any:
        try:
            return practice.check_answer(
                body.topic, body.problem_id, body.answer_latex, body.reference_latex
            )
        except Exception as error:
            return _internal_error("practice-check", error)

    @app.post("/api/tutor/chat", response_model=None)
    def tutor_chat_route(body: tutor_api.TutorRequest) -> Any:
        try:
            return tutor_api.chat_turn(body)
        except Exception as error:
            return _internal_error("tutor-chat", error)

    return app


app = create_app()
