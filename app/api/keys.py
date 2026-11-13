"""Invite-code admin CLI.

    python -m app.api.keys create "Ms. R - Lincoln HS" [--quota 100]
    python -m app.api.keys list
    python -m app.api.keys revoke tk_AbCd
"""
import argparse
from datetime import datetime, timezone

from sqlalchemy import select

from app.api.auth import hash_key, new_key
from app.api.db import ApiKey, SessionLocal, init_db


def create(label: str, quota: int | None = None) -> str:
    raw = new_key()
    with SessionLocal() as s:
        s.add(ApiKey(key_hash=hash_key(raw), prefix=raw[:7], label=label, daily_quota=quota))
        s.commit()
    return raw


def revoke(prefix: str) -> int:
    with SessionLocal() as s:
        keys = s.scalars(select(ApiKey).where(ApiKey.prefix == prefix[:7],
                                              ApiKey.revoked_at.is_(None))).all()
        for k in keys:
            k.revoked_at = datetime.now(timezone.utc)
        s.commit()
        return len(keys)


def main() -> None:
    p = argparse.ArgumentParser(prog="python -m app.api.keys")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("label")
    c.add_argument("--quota", type=int)
    sub.add_parser("list")
    r = sub.add_parser("revoke")
    r.add_argument("prefix")
    a = p.parse_args()

    init_db()
    if a.cmd == "create":
        print(create(a.label, a.quota))
        print("Shown once. Give this code to the tester; only its hash is stored.")
    elif a.cmd == "revoke":
        print(f"revoked {revoke(a.prefix)} key(s)")
    else:
        with SessionLocal() as s:
            for k in s.scalars(select(ApiKey).order_by(ApiKey.id)):
                state = "revoked" if k.revoked_at else "active"
                print(f"{k.prefix}…  {state:8} quota={k.daily_quota or 'default'}  {k.label}")


if __name__ == "__main__":
    main()
