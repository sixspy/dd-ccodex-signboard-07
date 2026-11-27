"""写入短锁，防并发双写。"""
from __future__ import annotations

import sqlite3
import time
from fastapi import APIRouter, Header, HTTPException

from auth import current_user, require_writer
from db import connect

router = APIRouter(prefix="/api/locks", tags=["locks"])


def acquire(lock_key: str, holder: str, ttl_sec: int = 20) -> None:
    now = time.time()
    with connect() as conn:
        row = conn.execute(
            "SELECT holder, expires_at FROM write_locks WHERE lock_key=?",
            (lock_key,),
        ).fetchone()
        if row and row["expires_at"] > now and row["holder"] != holder:
            raise HTTPException(409, f"资源锁定中：{row['holder']}")
        conn.execute(
            "INSERT INTO write_locks(lock_key,holder,expires_at) VALUES(?,?,?) "
            "ON CONFLICT(lock_key) DO UPDATE SET holder=excluded.holder, expires_at=excluded.expires_at",
            (lock_key, holder, now + ttl_sec),
        )
        conn.commit()


def acquire_exclusive(lock_key: str, holder: str, ttl_sec: int = 20) -> None:
    """严格互斥：靠 write_locks.lock_key 唯一键裁决，同 holder 可重入。

    与 acquire 的 upsert 不同，这里冲突时绝不覆盖既有持锁人——
    并发双写在数据库层一票胜出、一票 IntegrityError，杜绝 check-then-act 双成。
    返回 None 表示持锁成功；抛 409 表示成为败方，调用方负责留争用痕。
    """
    now = time.time()
    with connect() as conn:
        row = conn.execute(
            "SELECT holder, expires_at FROM write_locks WHERE lock_key=?",
            (lock_key,),
        ).fetchone()
        if row and row["expires_at"] > now and row["holder"] == holder:
            return  # 同持锁人重入
        if row and row["expires_at"] <= now:
            conn.execute("DELETE FROM write_locks WHERE lock_key=?", (lock_key,))
        try:
            conn.execute(
                "INSERT INTO write_locks(lock_key,holder,expires_at) VALUES(?,?,?)",
                (lock_key, holder, now + ttl_sec),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            holder_now = conn.execute(
                "SELECT holder FROM write_locks WHERE lock_key=?", (lock_key,)
            ).fetchone()
            who = holder_now["holder"] if holder_now else "未知持锁人"
            raise HTTPException(409, f"资源锁定中：{who}") from exc


def release(lock_key: str, holder: str) -> None:
    with connect() as conn:
        conn.execute(
            "DELETE FROM write_locks WHERE lock_key=? AND holder=?",
            (lock_key, holder),
        )
        conn.commit()


@router.post("/acquire")
def api_acquire(body: dict, authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    require_writer(user)
    key = (body.get("lock_key") or "").strip()
    if not key:
        raise HTTPException(400, "缺少 lock_key")
    acquire(key, user["username"], int(body.get("ttl_sec") or 20))
    return {"ok": True, "lock_key": key, "holder": user["username"]}


@router.post("/release")
def api_release(body: dict, authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    require_writer(user)
    key = (body.get("lock_key") or "").strip()
    release(key, user["username"])
    return {"ok": True}
