"""Request models for the practice routes: POST /api/practice/steps and /api/practice/check.

The routes in server/app.py call core/practice.py. Length and character checks on the typed
answer happen in core/practice.py, so a bad answer returns unable_to_verify, not a 422.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class StepsRequest(BaseModel):
    topic: str
    problem_id: str


class CheckRequest(BaseModel):
    topic: str = ""
    problem_id: Optional[str] = None
    answer_latex: str
    reference_latex: Optional[str] = None
