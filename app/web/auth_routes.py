import secrets

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from psycopg import IntegrityError
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from app.repositories import auth as repository
from app.services import auth as service
from app.web.routes import context, templates
from app.web.security import check_csrf, current_user

router = APIRouter()


def login_page(
    request: Request, error: str = "", username: str = "", status: int = 200
) -> HTMLResponse:
    token = secrets.token_urlsafe(32)
    response = templates.TemplateResponse(
        request=request,
        name="login.html",
        status_code=status,
        context={"error": error, "username": username, "login_csrf": token},
    )
    response.set_cookie(
        "rd_login_csrf",
        token,
        httponly=True,
        samesite="strict",
        max_age=1800,
        path="/login",
        secure=request.url.scheme == "https",
    )
    return response


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request) -> Response:
    if getattr(request.state, "user", None):
        return RedirectResponse("/", status_code=303)
    return login_page(request)


@router.post("/login")
async def login(request: Request) -> Response:
    form = dict(await request.form(max_fields=5, max_files=0))
    supplied = str(form.get("_csrf", ""))
    expected = request.cookies.get("rd_login_csrf", "")
    if not expected or not secrets.compare_digest(expected.encode(), supplied.encode()):
        return login_page(
            request, "Обновите страницу входа и повторите попытку", status=403
        )
    username = str(form.get("username", "")).strip().lower()
    password = str(form.get("password", ""))
    if not 1 <= len(username) <= 64 or not 1 <= len(password) <= 1024:
        return login_page(request, "Проверьте логин и пароль", username, 422)
    token = await service.login(request.app.state.db_pool, username, password)
    if token is None:
        return login_page(request, "Неверный логин или пароль", username, 401)
    old = request.cookies.get(repository.COOKIE)
    if old:
        await repository.delete_session(request.app.state.db_pool, old)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        repository.COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=8 * 3600,
        secure=request.url.scheme == "https",
    )
    response.delete_cookie("rd_login_csrf", path="/login")
    return response


@router.post("/logout")
async def logout(request: Request) -> Response:
    form = dict(await request.form(max_fields=5, max_files=0))
    check_csrf(request, form)
    await repository.delete_session(
        request.app.state.db_pool, request.cookies.get(repository.COOKIE, "")
    )
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(repository.COOKIE)
    return response


def require_director(request: Request) -> None:
    if current_user(request).role != "director":
        raise HTTPException(
            403, "Управление учётными записями доступно только руководителю"
        )


async def account_page(
    request: Request, values: dict | None = None, error: str = ""
) -> HTMLResponse:
    require_director(request)
    return templates.TemplateResponse(
        request=request,
        name="accounts.html",
        status_code=422 if error else 200,
        context=context(
            request,
            active="accounts",
            accounts=await repository.list_accounts(request.app.state.db_pool),
            employees=await repository.employee_options(
                request.app.state.db_pool, current_user(request)
            ),
            values=values or {},
            error=error,
        ),
    )


@router.get("/team/accounts", response_class=HTMLResponse)
async def accounts(request: Request) -> HTMLResponse:
    return await account_page(request)


@router.get("/team/accounts/{account_id}/edit", response_class=HTMLResponse)
async def account_edit(request: Request, account_id: int) -> HTMLResponse:
    require_director(request)
    rows = await repository.list_accounts(request.app.state.db_pool)
    row = next((row for row in rows if row["id"] == account_id), None)
    if row is None:
        raise HTTPException(404, "Учётная запись не найдена")
    return await account_page(request, {**row, "_id": account_id})


@router.post("/team/accounts/save")
async def account_save(request: Request) -> Response:
    require_director(request)
    form = dict(await request.form(max_fields=10, max_files=0))
    check_csrf(request, form)
    password = str(form.pop("password", ""))
    try:
        account_id = int(form["_id"]) if form.get("_id") else None
        values = service.AccountInput(
            username=str(form.get("username", "")).strip().lower(),
            employee_id=form.get("employee_id"),
            role=form.get("role"),
            active=form.get("active") == "on",
        ).model_dump()
        employees = await repository.employee_options(
            request.app.state.db_pool, current_user(request)
        )
        if values["employee_id"] not in employees:
            raise ValueError("Сотрудник не найден")
        if (
            password
            and not 10 <= len(password) <= 1024
            or not account_id
            and not password
        ):
            raise ValueError("Укажите пароль длиной от 10 до 1024 символов")
        values["password_hash"] = (
            await run_in_threadpool(service.passwords.hash, password)
            if password
            else None
        )
        await repository.save_account(request.app.state.db_pool, values, account_id)
    except ValidationError:
        return await account_page(
            request,
            form,
            "Проверьте поля. Логин: 3–64 латинских символа, цифры, точка, дефис или подчёркивание.",
        )
    except (ValueError, IntegrityError) as exc:
        error = (
            "Логин или сотрудник уже связан с другой учётной записью"
            if isinstance(exc, IntegrityError)
            else str(exc)
        )
        return await account_page(request, form, error)
    return RedirectResponse("/team/accounts", status_code=303)
