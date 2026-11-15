import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic import Field as PydanticField

from app.core.catalog import Entity
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
    pool: Any, entity: Entity, raw: dict, record_id: int | None = None
) -> tuple[int | None, dict[str, str]]:
    values, errors = validate(entity, raw)
    for field in entity.fields:
        if (
            field.reference
            and values.get(field.key)
            and field.key not in errors
            and not await repository.get_record(
                pool, field.reference, values[field.key]
            )
        ):
            errors[field.key] = "Запись не найдена. Выберите другую"
    if errors:
        return None, errors
    return await repository.save_record(pool, entity.key, values, record_id), {}
