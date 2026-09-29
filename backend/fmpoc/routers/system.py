from __future__ import annotations

import secrets
import threading

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from .. import VERSION
from ..deps import PRE_CSRF_COOKIE, SESSION_COOKIE, Ctx, auth_ctx, get_ctx, get_db
from ..config import build_info
from ..errors import AppError
from ..permissions import ADMINISTRATOR
from ..schemas import InitializeIn
from ..security.passwords import policy_errors
from ..services import auth as auth_svc
from ..services import bootstrap
from .auth import set_session_cookie

router = APIRouter(prefix="/api", tags=["system"])
_init_lock = threading.Lock()


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/system/status")
def status(request: Request, response: Response, db: Session = Depends(get_db)):
    initialized = bootstrap.is_initialized(db)
    ws = bootstrap.current_workspace(db) if initialized else None
    s = request.app.state.settings
    return {"initialized": initialized, "workspace_name": ws.name if ws else None, "version": VERSION,
            "mode": s.mode, "insecure_transport_warning": request.app.state.insecure_transport_warning}


@router.post("/system/initialize")
def initialize(body: InitializeIn, request: Request, response: Response, db: Session = Depends(get_db),
               ctx: Ctx = Depends(get_ctx)):
    if body.password != body.password_confirmation:
        raise AppError(422, "VALIDATION_ERROR", "Password and confirmation do not match.",
                       errors=[{"field": "password_confirmation", "message": "Passwords do not match."}])
    errs = policy_errors(body.password, body.admin_username)
    if errs:
        raise AppError(422, "PASSWORD_POLICY", " ".join(errs), errors=[{"field": "password", "message": e} for e in errs])
    settings = request.app.state.settings
    with _init_lock:
        try:
            admin = bootstrap.initialize(db, settings, ctx, workspace_name=body.workspace_name,
                                         username=body.admin_username, email=body.admin_email, password=body.password)
            token, sess = auth_svc.create_session(db, settings, admin)
            db.commit()
        except Exception:
            db.rollback()
            raise
    from ..security import crypto
    request.app.state.key = crypto.load_key(settings.secrets_dir)
    set_session_cookie(request, response, token)
    response.delete_cookie(PRE_CSRF_COOKIE, path="/")
    return {"initialized": True, "username": admin.username}


def version_payload(request: Request) -> dict:
    s = request.app.state.settings
    return {"version": VERSION, "build": build_info(), "mode": s.mode}


@router.get("/system/version")
def version(request: Request, ctx: Ctx = Depends(auth_ctx)):
    """v1.4 CR-022: version/build for every signed-in user (My Account → About); no network details."""
    return version_payload(request)


@router.get("/system/about")
def about(request: Request, ctx: Ctx = Depends(auth_ctx)):
    s = request.app.state.settings
    admin = ADMINISTRATOR in ctx.roles
    return {**version_payload(request), "bind_host": s.host if admin else None, "port": s.port if admin else None,
            "backup_notice": "Backup/restore is not provided in the POC. You are responsible for protecting the "
                             "application data directory (database, attachments and the portable encryption key "
                             "in secrets/) against machine or disk loss. All three are required for recovery.",
            "insecure_transport_warning": request.app.state.insecure_transport_warning}


__all__ = ["SESSION_COOKIE", "secrets"]
