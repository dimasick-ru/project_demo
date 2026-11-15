import secrets

from fastapi import HTTPException, Request
from psycopg import Error as DatabaseError
from psycopg_pool import PoolTimeout
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.core.access import ROLE_LABELS, User
from app.repositories import auth


def current_user(request: Request) -> User:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(401, "Войдите в систему")
    return user


def check_csrf(request: Request, form: dict) -> None:
    expected = current_user(request).csrf_token
    supplied = str(form.get("_csrf", ""))
    if not expected or not secrets.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(
            403, "Форма устарела. Обновите страницу и повторите действие"
        )


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path
        request.state.user = None
        if path == "/health" or path.startswith("/static/"):
            return await call_next(request)
        token = request.cookies.get(auth.COOKIE, "")
        if token:
            try:
                request.state.user = await auth.resolve_session(
                    request.app.state.db_pool, token
                )
            except (DatabaseError, PoolTimeout):
                # Never grant access when session storage is unavailable.
                return HTMLResponse(
                    "Сервис входа временно недоступен. Повторите позже.",
                    status_code=503,
                )
        if path == "/login":
            response = await call_next(request)
        elif request.state.user is None:
            if path.startswith("/items") or request.method != "GET":
                return JSONResponse({"detail": "Войдите в систему"}, status_code=401)
            response = RedirectResponse("/login", status_code=303)
            if request.headers.get("HX-Request") == "true":
                response.headers["HX-Redirect"] = "/login"
        elif (
            path.startswith("/items") or path in {"/docs", "/openapi.json", "/redoc"}
        ) and request.state.user.role != "director":
            return JSONResponse(
                {"detail": "Доступ разрешён только руководителю"}, status_code=403
            )
        elif request.state.user.role not in ROLE_LABELS:
            return JSONResponse({"detail": "Доступ запрещён"}, status_code=403)
        else:
            response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Vary"] = "Cookie, HX-Request"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response
