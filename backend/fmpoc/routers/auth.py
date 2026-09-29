from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from ..deps import PRE_CSRF_COOKIE, SESSION_COOKIE, Ctx, auth_ctx, get_ctx, get_db
from ..permissions import permissions_for
from ..schemas import ChangePasswordIn, LoginIn, PreferencesIn
from ..services import auth as svc

router = APIRouter(prefix="/api", tags=["auth"])


def _secure(request: Request) -> bool:
    mode = request.app.state.settings.secure_cookies
    return mode == "true" or (mode == "auto" and request.url.scheme == "https")


def set_session_cookie(request: Request, response: Response, token: str) -> None:
    s = request.app.state.settings
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="strict", secure=_secure(request), path="/",
                        max_age=s.session_absolute_hours * 3600)


@router.get("/auth/csrf")
def pre_auth_csrf(request: Request, response: Response):
    """Double-submit token for the unauthenticated login/initialize forms."""
    token = request.cookies.get(PRE_CSRF_COOKIE) or secrets.token_urlsafe(32)
    response.set_cookie(PRE_CSRF_COOKIE, token, httponly=False, samesite="strict", secure=_secure(request), path="/")
    return {"csrf_token": token}


def me_payload(ctx: Ctx) -> dict:
    u = ctx.user
    return {"id": u.id, "username": u.username, "email": u.email, "display_name": u.display_name,
            "security_domain": u.security_domain, "roles": sorted(ctx.roles), "permissions": sorted(ctx.perms),
            "theme": u.theme, "nav_collapsed": bool(u.nav_collapsed), "csrf_token": ctx.session.csrf_token}


@router.post("/auth/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db), ctx: Ctx = Depends(get_ctx)):
    s = request.app.state.settings
    user, token, sess = svc.login(db, s, request.app.state.limiter, ctx, body.username, body.password,
                                  request.cookies.get(SESSION_COOKIE))
    set_session_cookie(request, response, token)
    response.delete_cookie(PRE_CSRF_COOKIE, path="/")
    ctx.session, ctx.roles = sess, user.role_codes
    ctx.perms = permissions_for(ctx.roles)
    return me_payload(ctx)


@router.post("/auth/logout")
def logout(response: Response, db: Session = Depends(get_db), ctx: Ctx = Depends(auth_ctx)):
    svc.logout(db, ctx)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(ctx: Ctx = Depends(auth_ctx)):
    return me_payload(ctx)


@router.post("/auth/change-password")
def change_password(body: ChangePasswordIn, db: Session = Depends(get_db), ctx: Ctx = Depends(auth_ctx)):
    svc.change_own_password(db, ctx, body.current_password, body.new_password, body.new_password_confirmation)
    return {"ok": True, "other_sessions_revoked": True}


@router.put("/me/preferences")
def preferences(body: PreferencesIn, db: Session = Depends(get_db), ctx: Ctx = Depends(auth_ctx)):
    if body.theme is not None:
        ctx.user.theme = body.theme  # persisted per user (BR-UI-THEME-002)
    if body.nav_collapsed is not None:
        ctx.user.nav_collapsed = body.nav_collapsed  # v1.3 CR-014
    db.commit()
    return {"theme": ctx.user.theme, "nav_collapsed": bool(ctx.user.nav_collapsed)}
