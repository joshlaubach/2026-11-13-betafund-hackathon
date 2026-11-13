"""Invite-code access, per-code daily quota, and a global daily spend cap."""
import hashlib
import secrets
from datetime import datetime, time, timezone

from fastapi import Cookie, Depends, Header, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import ApiKey, Generation, get_session

COOKIE = "aimpg_key"


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_key() -> str:
    return "tk_" + secrets.token_urlsafe(24)


def lookup(s: Session, raw: str | None) -> ApiKey | None:
    if not raw:
        return None
    key = s.scalar(select(ApiKey).where(ApiKey.key_hash == hash_key(raw)))
    return key if key and key.revoked_at is None else None


def require_key(
    x_api_key: str | None = Header(default=None),
    aimpg_key: str | None = Cookie(default=None),
    s: Session = Depends(get_session),
) -> ApiKey:
    key = lookup(s, x_api_key or aimpg_key)
    if key is None:
        raise HTTPException(401, "missing or invalid invite code")
    return key


def _today_start() -> datetime:
    return datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)


def check_limits(s: Session, key: ApiKey, count: int) -> None:
    """Raise before any model call if this request would exceed quota or spend cap."""
    since = _today_start()
    spent = s.scalar(select(func.coalesce(func.sum(Generation.cost_usd), 0.0))
                     .where(Generation.created_at >= since))
    if spent >= settings.daily_spend_cap_usd:
        raise HTTPException(503, "daily generation budget reached; try again tomorrow")
    used = s.scalar(select(func.coalesce(func.sum(Generation.requested), 0))
                    .where(Generation.key_id == key.id, Generation.created_at >= since))
    quota = key.daily_quota or settings.key_daily_quota
    if used + count > quota:
        raise HTTPException(429, f"daily quota of {quota} problems reached for this invite code")
