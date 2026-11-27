"""变更历史。"""
from __future__ import annotations

from fastapi import APIRouter, Header

from auth import current_user
from db import connect, rows_to_list

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
def list_history(limit: int = 100, authorization: str | None = Header(default=None)):
    current_user(authorization)
    with connect() as conn:
        rows = rows_to_list(
            conn.execute(
                "SELECT * FROM change_history ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 300)),),
            ).fetchall()
        )
    return {"items": rows}


@router.get("/retirements")
def list_retirements(authorization: str | None = Header(default=None)):
    """signboard-07：退役联剔专账——retire 主票与逐清单 retire_kick 同账可溯。"""
    current_user(authorization)
    with connect() as conn:
        rows = rows_to_list(
            conn.execute(
                "SELECT * FROM change_history "
                "WHERE action IN ('retire','retire_kick') ORDER BY id DESC"
            ).fetchall()
        )
        contended = rows_to_list(
            conn.execute(
                "SELECT actor, action, payload, created_at FROM audit_log "
                "WHERE action='asset.retire_contend' ORDER BY id DESC"
            ).fetchall()
        )
    return {"items": rows, "contentions": contended}
