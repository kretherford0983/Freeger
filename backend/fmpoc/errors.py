"""Safe error model (BR-104). Responses never include stack traces, SQL, paths or secrets."""
from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("fmpoc")


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, **extra):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra


def not_found(what: str = "Record") -> AppError:
    return AppError(404, "NOT_FOUND", f"{what} not found.")


def forbidden(message: str = "You do not have permission to perform this action.") -> AppError:
    return AppError(403, "FORBIDDEN", message)


def validation(message: str, field: str | None = None) -> AppError:
    return AppError(422, "VALIDATION_ERROR", message, errors=[{"field": field, "message": message}] if field else [])


def conflict(code: str, message: str, **extra) -> AppError:
    return AppError(409, code, message, **extra)


class Warning_:
    """A warning that the caller must explicitly acknowledge by resubmitting with its code in
    `confirmations`."""

    def __init__(self, code: str, message: str, **details):
        self.code, self.message, self.details = code, message, details

    def as_dict(self):
        return {"code": self.code, "message": self.message, "details": self.details}


def require_confirmations(warnings: list[Warning_], confirmations: set[str] | list[str] | None) -> None:
    missing = [w for w in warnings if w.code not in set(confirmations or [])]
    if missing:
        raise AppError(
            409,
            "CONFIRMATION_REQUIRED",
            "This action requires explicit confirmation.",
            warnings=[w.as_dict() for w in missing],
        )


def _cid(request: Request) -> str:
    return getattr(request.state, "correlation_id", None) or uuid.uuid4().hex[:16]


def _body(code: str, message: str, request: Request, **extra):
    return {"error": {"code": code, "message": message, "correlation_id": _cid(request), **extra}}


def install_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(_body(exc.code, exc.message, request, **exc.extra), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        # Never echo submitted input values back (they may contain passwords/account numbers).
        errors = []
        for e in exc.errors():
            loc = [str(p) for p in e.get("loc", ()) if p not in ("body", "query", "path")]
            msg = str(e.get("msg", "Invalid value"))
            if e.get("type") == "extra_forbidden":
                msg = "This field is not permitted for this operation."
            errors.append({"field": ".".join(loc) or None, "message": msg[:300]})
        return JSONResponse(
            _body("VALIDATION_ERROR", "The request is invalid.", request, errors=errors), status_code=422
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = {401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED",
                413: "PAYLOAD_TOO_LARGE", 429: "RATE_LIMITED"}.get(exc.status_code, "HTTP_ERROR")
        msg = exc.detail if isinstance(exc.detail, str) and exc.status_code < 500 else "Request failed."
        return JSONResponse(_body(code, msg, request), status_code=exc.status_code)

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        # Detail goes to the protected server log only (engine uses hide_parameters=True).
        log.error("Unhandled error cid=%s type=%s", _cid(request), type(exc).__name__, exc_info=exc)
        return JSONResponse(
            _body("INTERNAL_ERROR", "An unexpected error occurred. Reference the correlation id.", request),
            status_code=500,
        )
