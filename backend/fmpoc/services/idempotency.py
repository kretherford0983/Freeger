"""v1.3 CR-011: one-time request keys.

The client generates a random key when a create form opens and sends it with every submit of that form. The key is
stored in the same database transaction as the records it created, so a repeated submit (double click, network
retry, resubmitted page) returns the records already created instead of creating them again.
"""
from __future__ import annotations

import time

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from ..errors import conflict
from ..models import RequestKey, utcnow


def _lookup(db: Session, ws_id: int, key: str) -> RequestKey | None:
    return db.scalar(select(RequestKey).where(RequestKey.workspace_id == ws_id, RequestKey.key == key))


def claim(db: Session, ctx, key: str | None, kind: str) -> list[int] | None:
    """Reserves `key` for this request. Returns the ids created by an earlier request with the same key (replay),
    or None when the caller should go ahead and create. Must run before any other write in the request."""
    if not key:
        return None
    for attempt in range(5):
        db.commit()  # start from a fresh snapshot so a concurrently committed key is visible
        row = _lookup(db, ctx.workspace_id, key)
        if row is not None:
            if row.kind != kind or not row.result_ids:
                raise conflict("REQUEST_KEY_REUSED", "This request key was already used for a different request.")
            return [int(x) for x in row.result_ids.split(",")]
        try:
            db.add(RequestKey(workspace_id=ctx.workspace_id, key=key, kind=kind, created_by_user_id=ctx.user.id,
                              created_at=utcnow()))
            db.flush()  # takes the write lock: a concurrent duplicate waits here, then sees the committed key
            return None
        except (IntegrityError, OperationalError):
            db.rollback()
            time.sleep(0.05 * (attempt + 1))
    raise conflict("REQUEST_IN_PROGRESS", "The same request is already being processed. Refresh the page.")


def complete(db: Session, ctx, key: str | None, ids: list[int]) -> None:
    if not key:
        return
    row = _lookup(db, ctx.workspace_id, key)
    if row is not None:
        row.result_ids = ",".join(str(i) for i in ids)
        db.flush()
