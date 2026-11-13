"""Request model and handler for POST /api/tutor/chat. The checks and replies live in core/tutor.py."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from core import tutor

Mode = Literal["live", "replay", "fake"]
DEFAULT_MODE = "replay"


class TutorRequest(BaseModel):
    message: str  # length and control characters are checked by core/tutor.py, not here
    history: list[Any] = Field(default_factory=list)  # each turn is checked by core/tutor.py
    context: Optional[dict[str, Any]] = None  # validated by core/tutor.py
    mode: Mode = DEFAULT_MODE


def chat_turn(body: TutorRequest) -> dict[str, Any]:
    """One tutor reply with its sources and validated actions, or {"status": "error"} with the reason."""
    return tutor.chat(body.message, body.history, body.context, body.mode)
