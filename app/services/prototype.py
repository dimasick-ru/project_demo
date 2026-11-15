import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic import Field as PydanticField

from app.core.access import OWNED, PARENTS, AccessDeniedError, User
from app.core.catalog import Entity
from app.repositories import auth as auth_repository
from app.repositories import prototype as repository


class TextValue(BaseModel):
    value: str = PydanticField(max_length=10000)


class NumberValue(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    value: Decimal = PydanticField(ge=0, max_digits=14, decimal_places=4)


class MoneyValue(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    value: Decimal = PydanticField(ge=0, max_digits=14, decimal_places=2)


def validate(entity: Entity, raw: dict) -> tuple[dict, dict[str, str]]:
    values: dict[str, Any] = {}
    errors = {}
    for field in entity.fields:
        value = str(raw.get(field.key, "")).strip()
        if not value:
            values[field.key] = [] if field.kind == "json" else None
            if field.required:
                errors[field.key] = "Заполните это поле"
            continue
        try:
            if field.kind == "money":
                result = MoneyValue(value=Decimal(value.replace(",", "."))).value
            elif field.kind == "number":
                result = NumberValue(value=Decimal(value.replace(",", "."))).value
            elif field.kind == "reference":
                result = int(value)
                if result <= 0:
                    raise ValueError
            elif field.kind == "date":
                result = date.fromisoformat(value)
            elif field.kind == "datetime-local":
                result = datetime.fromisoformat(value)
            elif field.kind == "json":
                result = json.loads(value, parse_float=Decimal)
                if not isinstance(result, list) or not all(
                    isinstance(p, dict) for p in result
                ):
                    raise ValueError
                # Jsonb's standard serializer does not support Decimal.
                result = json.loads(value)
                json.dumps(result, allow_nan=False)
            else:
                result = TextValue(value=value).value
            values[field.key] = result
        except (ValueError, TypeError, InvalidOperation, ValidationError):
            errors[field.key] = {
                "money": "Введите сумму от 0, не более двух знаков после запятой",
                "number": "Введите число от 0, не более четырёх знаков после запятой",
                "json": "Введите JSON-массив объектов, например []",
                "reference": "Выберите запись из списка",
            }.get(field.kind, "Проверьте значение поля")
    return values, errors


async def save(
    pool: Any, entity: Entity, raw: dict, user: User, record_id: int | None = None
) -> tuple[int | None, dict[str, str]]:
    values, errors = validate(entity, raw)
    referenced = {}
    for field in entity.fields:
        if not field.reference or not values.get(field.key) or field.key in errors:
            continue
        if field.reference == "employees":
            options = await auth_repository.employee_options(pool, user)
            row = {"id": values[field.key]} if values[field.key] in options else None
        else:
            row = await repository.get_record(
                pool, field.reference, values[field.key], user
            )
        if row is None:
            if user.role == "manager":
                raise AccessDeniedError("Выбрана запись, к которой у вас нет доступа")
            errors[field.key] = "Запись не найдена. Выберите другую"
        else:
            referenced[field.key] = row
    if entity.key in OWNED:
        if user.role == "manager":
            values["owner_employee_id"] = user.employee_id
            if raw.get("owner_employee_id") not in (None, "", str(user.employee_id)):
                raise AccessDeniedError(
                    "Менеджер не может назначить другого ответственного"
                )
        elif entity.key in PARENTS and referenced.get(PARENTS[entity.key][0]):
            values["owner_employee_id"] = referenced[PARENTS[entity.key][0]].get(
                "owner_employee_id"
            )
        else:
            owner = str(raw.get("owner_employee_id", "")).strip()
            options = await auth_repository.manager_options(pool)
            if not owner:
                values["owner_employee_id"] = None
            elif not owner.isdigit() or int(owner) not in options:
                errors["owner_employee_id"] = "Выберите менеджера из списка"
            else:
                values["owner_employee_id"] = int(owner)
    if user.role == "manager" and entity.key == "sales" and "positions" not in errors:
        allowed = await repository.list_records(pool, "nomenclature", user)
        allowed_names = {row["name"] for row in allowed}
        for position in values.get("positions", []):
            if position.get("номенклатура") not in allowed_names:
                raise AccessDeniedError(
                    "Позиции продажи должны содержать только ваши товары и услуги"
                )
    if errors:
        return None, errors
    return await repository.save_record(pool, entity.key, values, user, record_id), {}
