"""素材台账。"""
from __future__ import annotations

import time
from fastapi import APIRouter, Header, HTTPException

from audit_svc import write_audit, write_history
from auth import current_user, require_writer
from db import connect, row_to_dict, rows_to_list
from locks import acquire_exclusive, release
from models import ASSET_KIND_LABEL, ASSET_STATUS_LABEL, DEFAULT_DURATIONS
import playlists_svc
from validators import require_asset_status, require_code, require_kind, require_positive_int, require_title

router = APIRouter(prefix="/api/assets", tags=["assets"])

# 持锁窗口注入点（秒）：默认 0；仅互斥测试撑开胜方持锁窗口使用
RETIRE_LOCK_HOLD_SEC = 0.0


def _enrich(row: dict) -> dict:
    row["kind_label"] = ASSET_KIND_LABEL.get(row["kind"], row["kind"])
    row["status_label"] = ASSET_STATUS_LABEL.get(row["status"], row["status"])
    return row


@router.get("")
def list_assets(authorization: str | None = Header(default=None)):
    current_user(authorization)
    with connect() as conn:
        rows = rows_to_list(conn.execute("SELECT * FROM assets ORDER BY id DESC").fetchall())
    return {"items": [_enrich(r) for r in rows]}


@router.get("/{asset_id}")
def get_asset(asset_id: int, authorization: str | None = Header(default=None)):
    current_user(authorization)
    with connect() as conn:
        row = conn.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
    if not row:
        raise HTTPException(404, "素材不存在")
    return _enrich(dict(row))


@router.post("")
def create_asset(body: dict, authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    require_writer(user)
    code = require_code(body.get("code"), "素材编码")
    title = require_title(body.get("title"), "素材标题")
    kind = require_kind(body.get("kind"))
    duration = require_positive_int(
        body.get("duration_sec", DEFAULT_DURATIONS.get(kind, 10)), "时长", 1, 3600
    )
    resolution = (body.get("resolution") or "1920x1080").strip()
    status = require_asset_status(body.get("status") or "draft")
    checksum = (body.get("checksum") or "").strip()
    with connect() as conn:
        try:
            cur = conn.execute(
                "INSERT INTO assets(code,title,kind,duration_sec,resolution,status,owner,created_at,checksum) VALUES(?,?,?,?,?,?,?,?,?)",
                (code, title, kind, duration, resolution, status, user["username"], time.time(), checksum),
            )
            aid = cur.lastrowid
            conn.commit()
        except Exception as exc:
            raise HTTPException(409, f"素材编码冲突: {exc}") from exc
    write_history("asset", aid, "create", f"创建素材 {code}", user["username"])
    write_audit(user["username"], "asset.create", {"id": aid, "code": code})
    return {"id": aid, "code": code}


@router.patch("/{asset_id}")
def patch_asset(asset_id: int, body: dict, authorization: str | None = Header(default=None)):
    user = current_user(authorization)
    require_writer(user)
    with connect() as conn:
        row = conn.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
        if not row:
            raise HTTPException(404, "素材不存在")
        title = require_title(body.get("title", row["title"]), "素材标题")
        status = require_asset_status(body.get("status", row["status"]))
        duration = require_positive_int(body.get("duration_sec", row["duration_sec"]), "时长", 1, 3600)

        if status == "retired" and row["status"] != "retired":
            conn.rollback()  # 退役走独立票，先结束只读连接
            return retire_asset(asset_id, user)

        conn.execute(
            "UPDATE assets SET title=?, status=?, duration_sec=? WHERE id=?",
            (title, status, duration, asset_id),
        )
        conn.commit()
    write_history("asset", asset_id, "patch", f"更新素材状态={status}", user["username"])
    return {"ok": True}


@router.post("/{asset_id}/retire")
def retire_asset_endpoint(asset_id: int, authorization: str | None = Header(default=None)):
    """signboard-07 显式退役端点：甲路径同事务联剔，互斥裁决败方 409。"""
    user = current_user(authorization)
    require_writer(user)
    return retire_asset(asset_id, user)


def retire_asset(asset_id: int, user: dict) -> dict:
    """signboard-07 甲路径：退役与清单联剔同票同事务跨表账实。

    锁在事务开启前获取、事务落账后才释放——并发双请求在锁口当场分出胜负，
    败方 409 且留争用痕，不会被锁内幂等短路。串行重放（素材已退役）不抢锁，
    幂等返回 kicked_items=0。
    一票内完成 assets 置 retired + playlist_items 联剔；联剔抛错则整票 rollback，
    素材状态与清单条目都回到票前（正式零增回滚）。
    """
    actor = user["username"]
    lock_key = f"asset_retire:{asset_id}"

    with connect() as conn:
        row = conn.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
        if not row:
            raise HTTPException(404, "素材不存在")
        if row["status"] == "retired":
            # 串行重放的幂等通道：无争用，不抢锁
            return {
                "ok": True,
                "path": "official",
                "kicked_items": 0,
                "kicked_playlists": [],
                "note": "素材已退役，幂等返回",
            }

        try:
            acquire_exclusive(lock_key, actor)
        except HTTPException as exc:
            # 败方路径：正式区零增，争用痕必有（与胜方取舍分写）；
            # 载荷同时留败方（actor）与胜方持锁人（holder），两争用者均可溯
            holder = str(exc.detail).replace("资源锁定中：", "")
            write_audit(
                actor,
                "asset.retire_contend",
                {
                    "asset_id": asset_id,
                    "code": row["code"],
                    "loser": actor,
                    "holder": holder,
                    "reason": str(exc.detail),
                },
            )
            raise

        try:
            try:
                # 持锁窗口钩子：并发互斥测试可注入延迟，让胜方持锁覆盖败方争用时刻；
                # 生产默认零等待，不改变正常路径耗时
                delay = RETIRE_LOCK_HOLD_SEC
                if delay:
                    time.sleep(delay)
                conn.execute(
                    "UPDATE assets SET status='retired' WHERE id=?",
                    (asset_id,),
                )
                # 联剔在同一事务/同一连接内；抛错则整票回滚，素材状态与条目都回票前
                kicked = playlists_svc.kick_asset_items(conn, asset_id)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            kicked_codes = sorted({k["playlist_code"] for k in kicked})
        finally:
            release(lock_key, actor)

    # 票已提交后再写历史与审计（回滚时这些不会发生）
    write_history(
        "asset",
        asset_id,
        "retire",
        f"素材退役 {row['code']}，同事务联剔清单 {len(kicked_codes)} 张、条目 {len(kicked)} 条",
        actor,
    )
    for k in kicked:
        write_history(
            "playlist",
            k["playlist_id"],
            "retire_kick",
            f"退役联剔：素材 {row['code']} 移出清单 {k['playlist_code']} seq={k['seq']}",
            actor,
        )
    write_audit(
        actor,
        "asset.retire",
        {
            "id": asset_id,
            "code": row["code"],
            "kicked_items": len(kicked),
            "kicked_playlists": kicked_codes,
        },
    )
    return {
        "ok": True,
        "path": "official",
        "kicked_items": len(kicked),
        "kicked_playlists": kicked_codes,
    }
