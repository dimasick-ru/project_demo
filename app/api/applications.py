
from fastapi import APIRouter, HTTPException, Query, Request
from psycopg import IntegrityError
from pydantic import BaseModel, Field, model_validator

from app.repositories.aplications import get_aplication, get_aplications
from app.services.application_service import (
    change_application_status,
    register_aplication,
)

router = APIRouter(prefix="/applications", tags=["Заявки"])

class ClientCreate(BaseModel):
    full_name: str = Field(min_length=1)
    phone: str | None = None
    email: str | None = None


class ApplicationItem(BaseModel):
    nomenclature_id: int | None = Field(default=None, gt=0)
    program_id: int | None = Field(default=None, gt=0)
    quantity: int = Field(default=1, gt=0)

    @model_validator(mode="after")
    def validate_item(self):
        if (self.nomenclature_id is None) == (self.program_id is None):
            raise ValueError("Должен быть указан либо nomenclature_id, либо program_id")
        
        return self

class ApplicationCreate(BaseModel):
    client_id: int | None = Field(default=None, gt=0)
    client: ClientCreate | None = None
    employee_id: int | None = Field(default=None, gt=0)
    comment: str | None = None
    items: list[ApplicationItem] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_client(self):
        if (self.client_id is None) == (self.client is None):
            raise ValueError("Должен быть указан либо client_id, либо client")
        return self

@router.post("", status_code=201)
async def create_application(data: ApplicationCreate, request: Request):
    try:
        async with request.app.state.db_pool.connection() as conn:
            return await register_aplication(conn, data)
    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Неверная ссылка на: {exc}",
        ) from exc


class ApplicationStatusUpdate(BaseModel):
    status: str = Field(min_length=1)


@router.get("")
async def list_aplications(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0)
):

    async with request.app.state.db_pool.connection() as conn:
        return await get_aplications(conn, limit, offset)

@router.get("/{application_id}")
async def read_application(
    application_id: int,
    request: Request,
):
    async with request.app.state.db_pool.connection() as conn:
        application = await get_aplication(conn, application_id)

    if application is None:
        raise HTTPException(
            status_code=404,
            detail="Заявка не найдена",
        )

    return application


@router.patch("/{application_id}/status")
async def patch_application_status(
    application_id: int,
    data: ApplicationStatusUpdate,
    request: Request,
):
    async with request.app.state.db_pool.connection() as conn:
        result = await change_application_status(
            conn,
            application_id,
            data.status.strip(),
        )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Заявка не найдена",
        )

    return result