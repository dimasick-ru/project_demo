import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from psycopg import Error as DatabaseError
from psycopg_pool import AsyncConnectionPool
from starlette.concurrency import run_in_threadpool

from app.core.access import (
    OWNED,
    PARENTS,
    ROLE_LABELS,
    AccessDeniedError,
    User,
    can_read,
    can_write,
    require_access,
)
from app.core.catalog import ENTITIES, Entity
from app.repositories import auth as auth_repository
from app.repositories import prototype as repository
from app.services import prototype as service
from app.web.security import check_csrf, current_user

router = APIRouter()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def display(value: Any, kind: str = "text") -> str:
    if value is None or value == "":
        return "—"
    if kind == "money":
        return f"{Decimal(value):,.2f}".replace(",", " ") + " ₽"
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y · %H:%M")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, (list, dict)):
        return f"Позиций: {len(value)}"
    return str(value)


def input_value(value: Any, kind: str = "text") -> str:
    if value is None:
        return ""
    if kind == "json" and not isinstance(value, str):
        return json.dumps(value, ensure_ascii=False, indent=2)
    if isinstance(value, datetime):
        # Browsers reject datetime-local values with microsecond precision.
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


templates.env.filters["display"] = display
templates.env.filters["input_value"] = input_value


def entity_or_404(key: str) -> Entity:
    if key not in ENTITIES:
        raise HTTPException(404, "Раздел не найден")
    return ENTITIES[key]


def context(request: Request, **kwargs: Any) -> dict[str, Any]:
    user = getattr(request.state, "user", None)
    visible = {
        key: entity for key, entity in ENTITIES.items() if user and can_read(user, key)
    }
    return {
        "request": request,
        "entities": visible,
        "user": user,
        "role_labels": ROLE_LABELS,
        "writable": {key for key in visible if can_write(user, key)},
        "groups": tuple(dict.fromkeys(entity.group for entity in visible.values())),
        "active": "overview",
        **kwargs,
    }


async def lookup(
    pool: AsyncConnectionPool, entity: Entity, user: User
) -> dict[str, dict[int, str]]:
    result = {}
    for field in entity.fields:
        reference = field.reference or (
            "nomenclature" if field.kind == "json" else None
        )
        if reference and reference not in result:
            if reference == "employees":
                result[reference] = await auth_repository.employee_options(pool, user)
                continue
            rows = await repository.list_records(pool, reference, user)
            result[reference] = {
                row["id"]: str(row.get("name") or row.get("number") or row["id"])
                for row in rows
            }
    return result


@router.get("/", response_class=HTMLResponse)
async def overview(request: Request) -> HTMLResponse:
    pool = request.app.state.db_pool
    user = current_user(request)
    clients = await repository.list_records(pool, "clients", user)
    visits = await repository.list_records(pool, "visits", user)
    programs = await repository.list_records(pool, "programs", user)
    contracts = await repository.list_records(pool, "contracts", user)
    client_names = {row["id"]: row["name"] for row in clients}
    now = datetime.now()
    upcoming = sorted(
        (row for row in visits if row["starts_at"] >= now),
        key=lambda row: row["starts_at"],
    )[:5]
    return templates.TemplateResponse(
        request=request,
        name="overview.html",
        context=context(
            request,
            counts=[len(clients), len(visits), len(programs), len(contracts)],
            clients=clients[:5],
            visits=upcoming,
            client_names=client_names,
        ),
    )


@router.get("/workspace/{key}", response_class=HTMLResponse)
async def records(
    request: Request, key: str, q: str = "", saved: bool = False
) -> HTMLResponse:
    entity = entity_or_404(key)
    pool = request.app.state.db_pool
    user = current_user(request)
    require_access(user, key)
    rows = await repository.list_records(pool, key, user)
    references = await lookup(pool, entity, user)
    total = len(rows)
    if q:

        def matches(row: dict[str, Any]) -> bool:
            parts = [str(row["id"])]
            for field in entity.fields:
                value = row.get(field.key)
                if field.reference:
                    value = references[field.reference].get(value, "")
                parts.append(display(value, field.kind))
            return q.casefold() in " ".join(parts).casefold()

        rows = [row for row in rows if matches(row)]
    template = (
        "table.html" if request.headers.get("HX-Request") == "true" else "records.html"
    )
    return templates.TemplateResponse(
        request=request,
        name=template,
        context=context(
            request,
            active=key,
            entity=entity,
            rows=rows,
            total=total,
            references=references,
            q=q,
            saved=saved,
            owners=await auth_repository.manager_options(pool)
            if user.role != "manager" and key in OWNED
            else {},
        ),
    )


async def render_form(
    request: Request,
    entity: Entity,
    values: dict[str, Any],
    record_id: int | None = None,
    errors: dict[str, str] | None = None,
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="form.html",
        status_code=422 if errors else 200,
        context=context(
            request,
            active=entity.key,
            entity=entity,
            values=values,
            record_id=record_id,
            errors=errors or {},
            references=await lookup(
                request.app.state.db_pool, entity, current_user(request)
            ),
            show_owner=entity.key in OWNED
            and (entity.key not in PARENTS or entity.key == "sales")
            and current_user(request).role != "manager",
            owners=await auth_repository.manager_options(request.app.state.db_pool)
            if current_user(request).role != "manager"
            else {},
        ),
    )


@router.get("/workspace/{key}/new", response_class=HTMLResponse)
async def new_form(request: Request, key: str) -> HTMLResponse:
    entity = entity_or_404(key)
    require_access(current_user(request), key, write=True)
    return await render_form(request, entity, {})


@router.get("/workspace/{key}/{record_id}/edit", response_class=HTMLResponse)
async def edit_form(request: Request, key: str, record_id: int) -> HTMLResponse:
    entity = entity_or_404(key)
    user = current_user(request)
    require_access(user, key, write=True)
    row = await repository.get_record(request.app.state.db_pool, key, record_id, user)
    if row is None:
        raise HTTPException(404, "Запись не найдена")
    return await render_form(request, entity, row, record_id)


@router.post("/workspace/{key}/save", response_class=HTMLResponse)
async def save_form(request: Request, key: str) -> Response:
    entity = entity_or_404(key)
    user = current_user(request)
    require_access(user, key, write=True)
    form = dict(await request.form(max_fields=50, max_files=0))
    check_csrf(request, form)
    try:
        record_id = int(form["_id"]) if form.get("_id") else None
    except (ValueError, TypeError):
        raise HTTPException(422, "Некорректный идентификатор") from None
    if record_id is not None and not await repository.get_record(
        request.app.state.db_pool, key, record_id, user
    ):
        raise HTTPException(404, "Запись не найдена")
    try:
        saved_id, errors = await service.save(
            request.app.state.db_pool, entity, form, user, record_id
        )
    except DatabaseError:
        return await render_form(
            request,
            entity,
            form,
            record_id,
            {"_form": "Не удалось сохранить запись. Проверьте данные."},
        )
    if errors:
        return await render_form(request, entity, form, record_id, errors)
    if saved_id is None:
        raise HTTPException(404, "Запись не найдена")
    return RedirectResponse(f"/workspace/{key}?saved=true", status_code=303)


async def database_error(request: Request, exc: Exception) -> HTMLResponse:
    return await run_in_threadpool(
        templates.TemplateResponse,
        request=request,
        name="error.html",
        status_code=503,
        context=context(request),
    )


async def access_denied(request: Request, exc: AccessDeniedError) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="denied.html",
        status_code=403,
        context=context(request, message=str(exc)),
    )
