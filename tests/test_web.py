from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.core.catalog import ENTITIES
from app.main import app
from app.repositories import prototype as repository
from app.services.prototype import validate
from app.web.routes import input_value


@pytest.fixture
def web(monkeypatch):
    data = {key: [] for key in ENTITIES}
    data["clients"] = [
        {
            "id": 1,
            "name": "Тестовый клиент",
            "contact": "test@example.com",
            "status": "Новый",
            "screening": None,
        }
    ]
    data["programs"] = [
        {
            "id": 1,
            "name": "Программа",
            "description": "Описание",
            "included_services": "Занятия",
            "price": Decimal("12000.50"),
            "duration": "1 месяц",
        }
    ]
    data["visits"] = [
        {
            "id": 1,
            "client_id": 1,
            "employee_id": None,
            "starts_at": datetime.now() + timedelta(days=1),
            "purpose": "Знакомство",
            "contract_id": None,
            "status": "Запланирован",
        }
    ]

    async def listing(pool, key):
        return deepcopy(data[key])

    async def get(pool, key, record_id):
        return next(
            (deepcopy(row) for row in data[key] if row["id"] == record_id), None
        )

    async def save(pool, key, values, record_id=None):
        record_id = record_id or max((r["id"] for r in data[key]), default=0) + 1
        data[key] = [row for row in data[key] if row["id"] != record_id]
        data[key].insert(0, {"id": record_id, **values})
        return record_id

    monkeypatch.setattr(repository, "list_records", listing)
    monkeypatch.setattr(repository, "get_record", get)
    monkeypatch.setattr(repository, "save_record", save)
    app.state.db_pool = object()
    with TestClient(app, raise_server_exceptions=True) as client:
        yield client, data


@pytest.fixture(autouse=True)
def no_database_lifespan(monkeypatch):
    # Exercise the actual lifespan without requiring credentials or a database.
    class Pool:
        async def open(self):
            pass

        async def close(self):
            pass

    monkeypatch.setattr("app.main.create_db_poll", Pool)


def test_overview_and_local_assets(web):
    client, _ = web
    response = client.get("/")
    assert response.status_code == 200
    assert "Хороший день для заботы" in response.text
    assert "Тестовый клиент" in response.text
    for path in ("app.css", "app.js", "vendor/bootstrap.min.css", "vendor/htmx.min.js"):
        assert client.get(f"/static/{path}").status_code == 200


@pytest.mark.parametrize("key", ENTITIES)
def test_all_sections_and_forms(web, key):
    client, _ = web
    assert client.get(f"/workspace/{key}").status_code == 200
    response = client.get(f"/workspace/{key}/new")
    assert response.status_code == 200
    assert ENTITIES[key].title in response.text


def test_client_create_edit_search_and_escaping(web):
    client, data = web
    response = client.post(
        "/workspace/clients/save",
        data={
            "name": '<script>alert("test")</script>',
            "contact": "new@example.com",
        },
    )
    assert response.status_code == 200
    assert len(data["clients"]) == 2
    assert '<script>alert("test")</script>' not in response.text
    record_id = data["clients"][0]["id"]
    assert client.get(f"/workspace/clients/{record_id}/edit").status_code == 200
    response = client.post(
        "/workspace/clients/save",
        data={
            "_id": str(record_id),
            "name": "Обновлённый клиент",
            "contact": "changed@example.com",
        },
    )
    assert response.status_code == 200
    assert data["clients"][0]["contact"] == "changed@example.com"
    response = client.get(
        "/workspace/clients?q=Обновлённый", headers={"HX-Request": "true"}
    )
    assert "Обновлённый клиент" in response.text
    assert "Тестовый клиент" not in response.text
    assert "<!doctype" not in response.text


def test_invalid_fields_preserve_input(web):
    client, data = web
    response = client.post(
        "/workspace/programs/save", data={"name": "Новая", "price": "-1"}
    )
    assert response.status_code == 422
    assert "Новая" in response.text
    assert "Введите сумму от 0" in response.text
    assert len(data["programs"]) == 1
    response = client.post("/workspace/clients/save", data={"name": "  "})
    assert response.status_code == 422


def test_missing_reference_rejected(web):
    client, data = web
    response = client.post(
        "/workspace/contracts/save",
        data={
            "number": "Д-999",
            "client_id": "999",
            "program_id": "1",
        },
    )
    assert response.status_code == 422
    assert "Запись не найдена" in response.text
    assert not data["contracts"]


def test_not_found(web):
    client, _ = web
    assert client.get("/workspace/unknown").status_code == 404
    assert client.get("/workspace/clients/999/edit").status_code == 404
    assert (
        client.post(
            "/workspace/clients/save", data={"_id": 999, "name": "Имя"}
        ).status_code
        == 404
    )


def test_decimal_and_json_validation():
    values, errors = validate(
        ENTITIES["programs"], {"name": "Программа", "price": "123,45"}
    )
    assert not errors
    assert values["price"] == Decimal("123.45")
    for price in ("NaN", "Infinity", "12.345", "1000000000000"):
        _, errors = validate(
            ENTITIES["programs"], {"name": "Программа", "price": price}
        )
        assert "price" in errors
    for positions in ("{}", "[1]", '[{"price": NaN}]', "invalid"):
        _, errors = validate(
            ENTITIES["sales"], {"number": "П-1", "positions": positions}
        )
        assert "positions" in errors


def test_datetime_edit_value_is_browser_compatible():
    value = datetime(2026, 11, 16, 12, 30, 15, 123456)
    assert input_value(value, "datetime-local") == "2026-11-16T12:30:15"


def test_valid_contract_and_reference_search(web):
    client, data = web
    response = client.post(
        "/workspace/contracts/save",
        data={
            "number": "Д-1",
            "client_id": "1",
            "program_id": "1",
            "status": "Черновик",
        },
    )
    assert response.status_code == 200
    assert data["contracts"][0]["client_id"] == 1
    assert "Программа" in response.text
    assert "Д-1" in client.get("/workspace/contracts?q=Тестовый").text
