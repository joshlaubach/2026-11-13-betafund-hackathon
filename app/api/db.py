"""Generation log (no user data). Schema is created with create_all at startup."""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.config import settings


def _now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ApiKey(Base):
    __tablename__ = "api_key"
    id: Mapped[int] = mapped_column(primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    prefix: Mapped[str] = mapped_column(String(12))
    label: Mapped[str] = mapped_column(String(200))
    daily_quota: Mapped[int | None] = mapped_column(Integer)  # None = default from settings
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Generation(Base):
    __tablename__ = "generation"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, index=True)
    key_id: Mapped[int | None] = mapped_column(ForeignKey("api_key.id"), index=True)
    request: Mapped[dict] = mapped_column(JSON)
    course: Mapped[str] = mapped_column(String(32))
    topic_ids: Mapped[list] = mapped_column(JSON)
    requested: Mapped[int] = mapped_column(Integer)
    returned: Mapped[int] = mapped_column(Integer, default=0)
    shortfall_reason: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(64))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)


class Attempt(Base):
    __tablename__ = "attempt"
    id: Mapped[int] = mapped_column(primary_key=True)
    generation_id: Mapped[str] = mapped_column(ForeignKey("generation.id"), index=True)
    topic_id: Mapped[str] = mapped_column(String(80), index=True)
    strategy: Mapped[str] = mapped_column(String(16))
    raw_output: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16))  # passed | failed | timeout | invalid
    method: Mapped[str | None] = mapped_column(String(64))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    repair_attempt: Mapped[int] = mapped_column(Integer, default=0)
    verify_ms: Mapped[int | None] = mapped_column(Integer)
    difficulty_features: Mapped[dict | None] = mapped_column(JSON)
    assigned_level: Mapped[int | None] = mapped_column(Integer)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)


def _url(url: str) -> str:
    # Neon/Vercel hand out postgres:// or postgresql://; SQLAlchemy needs the driver name.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


engine = create_engine(_url(settings.database_url), pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session():
    """FastAPI dependency: one session per request, closed afterwards."""
    with SessionLocal() as s:
        yield s

