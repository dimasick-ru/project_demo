from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator
from psycopg import IntegrityError

from app.services.application_service import register_aplication

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