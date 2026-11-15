"""Opt-in authorization checks against PostgreSQL; only temporary records are removed.

Run: $env:RUN_DB_TESTS='1'; python -m pytest tests/test_access_db.py
"""

import asyncio
import os
import re
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.types.json import Jsonb
from pwdlib import PasswordHash

from app.core.access import OWNED
from app.core.catalog import ENTITIES
from app.core.config import get_settings
from app.main import app
from app.repositories.auth import COOKIE, token_hash

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_TESTS") != "1", reason="Requires local PostgreSQL"
)


def csrf(html: str) -> str:
    return re.search(r'name="_csrf" value="([^"]+)"', html).group(1)


@pytest.fixture(scope="module")
def dataset():
    settings = get_settings()
    prefix = "access_" + secrets.token_hex(5)
    inserted = []
    users = {}
    records = {}
    password = "Temporary-test-password-2026"
    hasher = PasswordHash.recommended()
    with psycopg.connect(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password.get_secret_value(),
        autocommit=True,
    ) as conn:

        def insert(key, values):
            columns = list(values)
            row = conn.execute(
                sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
                    sql.Identifier("prototype", key),
                    sql.SQL(",").join(map(sql.Identifier, columns)),
                    sql.SQL(",").join(sql.Placeholder() for _ in columns),
                ),
                list(values.values()),
            ).fetchone()
            inserted.append((key, row[0]))
            return row[0]

        try:
            for role in ("manager1", "manager2", "administrator", "director"):
                employee_id = insert("employees", {"name": f"{prefix}_{role}_employee"})
                username = f"{prefix}_{role}"
                account_id = insert(
                    "accounts",
                    {
                        "employee_id": employee_id,
                        "username": username,
                        "role": "manager" if role.startswith("manager") else role,
                        "password_hash": hasher.hash(password),
                    },
                )
                users[role] = {
                    "id": account_id,
                    "employee_id": employee_id,
                    "username": username,
                    "password": password,
                }
            extra_employee = insert("employees", {"name": f"{prefix}_extra_employee"})
            program_id = insert(
                "programs", {"name": prefix + "_program", "price": Decimal("100.00")}
            )
            for role in ("manager1", "manager2"):
                owner = users[role]["employee_id"]
                for key in (
                    "clients",
                    "nomenclature",
                    "contracts",
                    "visits",
                    "sales",
                    "payments",
                    "stock",
                    "movements",
                    "provided_services",
                    "service_log",
                ):
                    values = {"owner_employee_id": owner}
                    for field in ENTITIES[key].fields:
                        if field.kind == "reference":
                            values[field.key] = (
                                owner
                                if field.reference == "employees"
                                else program_id
                                if field.reference == "programs"
                                else records[(role, field.reference)]
                            )
                        elif field.kind == "json":
                            values[field.key] = Jsonb([])
                        elif field.kind in {"number", "money"}:
                            values[field.key] = Decimal("10.00")
                        elif field.kind == "date":
                            values[field.key] = datetime.now().date()
                        elif field.kind == "datetime-local":
                            values[field.key] = datetime.now() + timedelta(days=1)
                        else:
                            values[field.key] = f"{prefix}_{role}_{key}_{field.key}"
                    records[(role, key)] = insert(key, values)
            yield {
                "conn": conn,
                "users": users,
                "records": records,
                "prefix": prefix,
                "inserted": inserted,
                "extra_employee": extra_employee,
            }
        finally:
            ids = [user["id"] for user in users.values()]
            if ids:
                conn.execute(
                    "DELETE FROM prototype.sessions WHERE account_id=ANY(%s)", (ids,)
                )
            for key, record_id in reversed(inserted):
                conn.execute(
                    sql.SQL("DELETE FROM {} WHERE id=%s").format(
                        sql.Identifier("prototype", key)
                    ),
                    (record_id,),
                )


@contextmanager
def logged_in(dataset, role):
    user = dataset["users"][role]
    with TestClient(
        app, backend_options={"loop_factory": asyncio.SelectorEventLoop}
    ) as client:
        page = client.get("/login")
        response = client.post(
            "/login",
            data={
                "username": user["username"],
                "password": user["password"],
                "_csrf": csrf(page.text),
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "httponly" in response.headers["set-cookie"].lower()
        yield client


@pytest.mark.parametrize("key", sorted(OWNED))
def test_manager_record_isolation(dataset, key):
    own = dataset["records"][("manager1", key)]
    foreign = dataset["records"][("manager2", key)]
    with logged_in(dataset, "manager1") as client:
        response = client.get(f"/workspace/{key}")
        assert response.status_code == 200
        assert f"/workspace/{key}/{own}/edit" in response.text
        assert f"/workspace/{key}/{foreign}/edit" not in response.text
        assert client.get(f"/workspace/{key}/{foreign}/edit").status_code == 404
        token = csrf(client.get(f"/workspace/{key}/{own}/edit").text)
        response = client.post(
            f"/workspace/{key}/save", data={"_id": foreign, "_csrf": token}
        )
        assert response.status_code == 404


@pytest.mark.parametrize("role", ["manager1", "administrator"])
def test_restricted_sections_api_and_reference_lists(dataset, role):
    with logged_in(dataset, role) as client:
        for key in (
            "employees",
            "suppliers",
            "orders",
            "employee_activity",
            "work_log",
        ):
            assert client.get(f"/workspace/{key}").status_code == 403
            assert client.get(f"/workspace/{key}/new").status_code == 403
            assert client.post(f"/workspace/{key}/save", data={}).status_code == 403
        assert client.get("/team/accounts").status_code == 403
        assert client.post("/team/accounts/save", data={}).status_code == 403
        assert client.get("/items").status_code == 403
        assert (
            client.post("/items", json={"name": "test", "price": 1}).status_code == 403
        )
        assert client.get("/openapi.json").status_code == 403
        assert client.get("/workspace/programs").status_code == 200
        assert client.get("/workspace/programs/new").status_code == 403
        assert client.post("/workspace/programs/save", data={}).status_code == 403


def test_administrator_sees_both_managers(dataset):
    with logged_in(dataset, "administrator") as client:
        for key in OWNED:
            response = client.get(f"/workspace/{key}")
            assert response.status_code == 200
            for role in ("manager1", "manager2"):
                record_id = dataset["records"][(role, key)]
                assert f"/workspace/{key}/{record_id}/edit" in response.text
                assert (
                    client.get(f"/workspace/{key}/{record_id}/edit").status_code == 200
                )


def test_director_has_all_sections(dataset):
    with logged_in(dataset, "director") as client:
        for key in ENTITIES:
            assert client.get(f"/workspace/{key}").status_code == 200
            assert client.get(f"/workspace/{key}/new").status_code == 200
        response = client.get("/team/accounts")
        assert response.status_code == 200
        assert "password_hash" not in response.text
        assert dataset["users"]["manager1"]["password"] not in response.text


def test_manager_dashboard_search_and_choices_do_not_leak(dataset):
    prefix = dataset["prefix"]
    with logged_in(dataset, "manager1") as client:
        assert f"{prefix}_manager2_clients_name" not in client.get("/").text
        response = client.get(
            "/workspace/clients",
            params={"q": f"{prefix}_manager2"},
            headers={"HX-Request": "true"},
        )
        assert f"{prefix}_manager2" not in response.text
        response = client.get("/workspace/visits/new")
        assert f"{prefix}_manager1_clients_name" in response.text
        assert f"{prefix}_manager2_clients_name" not in response.text
        assert f"{prefix}_manager2_employee" not in response.text
        assert (
            f"{prefix}_manager2_nomenclature_name"
            not in client.get("/workspace/sales/new").text
        )


def test_manager_cannot_forge_links_owner_or_csrf(dataset):
    users, records = dataset["users"], dataset["records"]
    with logged_in(dataset, "manager1") as client:
        token = csrf(client.get("/workspace/clients/new").text)
        assert (
            client.post(
                "/workspace/clients/save",
                data={
                    "name": "Forged",
                    "_csrf": token,
                    "owner_employee_id": users["manager2"]["employee_id"],
                },
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/workspace/visits/save",
                data={
                    "client_id": records[("manager2", "clients")],
                    "starts_at": "2026-11-16T12:00",
                    "_csrf": token,
                },
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/workspace/visits/save",
                data={
                    "client_id": records[("manager1", "clients")],
                    "employee_id": users["manager2"]["employee_id"],
                    "starts_at": "2026-11-16T12:00",
                    "_csrf": token,
                },
            ).status_code
            == 403
        )
        foreign_name = f"{dataset['prefix']}_manager2_nomenclature_name"
        import json

        assert (
            client.post(
                "/workspace/sales/save",
                data={
                    "number": "forged",
                    "_csrf": token,
                    "positions": json.dumps([{"номенклатура": foreign_name}]),
                },
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/workspace/clients/save", data={"name": "Missing token"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/workspace/clients/save",
                data={"name": "Wrong token", "_csrf": "wrong"},
            ).status_code
            == 403
        )


def test_new_client_gets_session_employee_owner(dataset):
    name = dataset["prefix"] + "_new_client"
    with logged_in(dataset, "manager1") as client:
        token = csrf(client.get("/workspace/clients/new").text)
        response = client.post(
            "/workspace/clients/save",
            data={"name": name, "_csrf": token},
            follow_redirects=False,
        )
        assert response.status_code == 303
        row = (
            dataset["conn"]
            .execute(
                "SELECT id,owner_employee_id FROM prototype.clients WHERE name=%s",
                (name,),
            )
            .fetchone()
        )
        dataset["inserted"].append(("clients", row[0]))
        assert row[1] == dataset["users"]["manager1"]["employee_id"]


def test_reassignment_moves_related_records_without_stale_access(dataset):
    root = dataset["records"][("manager1", "clients")]
    visit = dataset["records"][("manager1", "visits")]
    conn = dataset["conn"]
    try:
        conn.execute(
            "UPDATE prototype.clients SET owner_employee_id=%s WHERE id=%s",
            (dataset["users"]["manager2"]["employee_id"], root),
        )
        with logged_in(dataset, "manager1") as client:
            assert client.get(f"/workspace/visits/{visit}/edit").status_code == 404
        with logged_in(dataset, "manager2") as client:
            assert client.get(f"/workspace/visits/{visit}/edit").status_code == 200
    finally:
        conn.execute(
            "UPDATE prototype.clients SET owner_employee_id=%s WHERE id=%s",
            (dataset["users"]["manager1"]["employee_id"], root),
        )


def test_logout_expiration_and_disabled_account(dataset):
    with logged_in(dataset, "manager1") as client:
        cookie = client.cookies.get(COOKIE)
        row = (
            dataset["conn"]
            .execute(
                "SELECT token_hash FROM prototype.sessions WHERE token_hash=%s",
                (token_hash(cookie),),
            )
            .fetchone()
        )
        assert row and row[0] != cookie
        token = csrf(client.get("/workspace/clients/new").text)
        assert (
            client.post(
                "/logout", data={"_csrf": token}, follow_redirects=False
            ).status_code
            == 303
        )
        assert client.get("/", follow_redirects=False).status_code == 303
    with logged_in(dataset, "manager1") as client:
        dataset["conn"].execute(
            "UPDATE prototype.sessions SET expires_at=CURRENT_TIMESTAMP-INTERVAL '1 second' WHERE token_hash=%s",
            (token_hash(client.cookies.get(COOKIE)),),
        )
        assert client.get("/", follow_redirects=False).status_code == 303
    with logged_in(dataset, "manager1") as client:
        account_id = dataset["users"]["manager1"]["id"]
        try:
            dataset["conn"].execute(
                "UPDATE prototype.accounts SET active=FALSE WHERE id=%s", (account_id,)
            )
            assert client.get("/", follow_redirects=False).status_code == 303
        finally:
            dataset["conn"].execute(
                "UPDATE prototype.accounts SET active=TRUE WHERE id=%s", (account_id,)
            )


def test_invalid_login_and_login_csrf(dataset):
    with TestClient(
        app, backend_options={"loop_factory": asyncio.SelectorEventLoop}
    ) as client:
        token = csrf(client.get("/login").text)
        response = client.post(
            "/login",
            data={
                "username": dataset["users"]["manager1"]["username"],
                "password": "incorrect",
                "_csrf": token,
            },
        )
        assert response.status_code == 401
        assert "Неверный логин или пароль" in response.text
        assert (
            client.post(
                "/login", data={"username": "unknown", "password": "incorrect"}
            ).status_code
            == 403
        )


def test_director_account_management_revokes_sessions(dataset):
    target = dataset["users"]["manager2"]
    with logged_in(dataset, "director") as client:
        token = csrf(client.get("/team/accounts").text)
        new_username = dataset["prefix"] + "_created"
        response = client.post(
            "/team/accounts/save",
            data={
                "_csrf": token,
                "username": new_username,
                "employee_id": dataset["extra_employee"],
                "role": "manager",
                "active": "on",
                "password": "Temporary-new-password-2026",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        row = (
            dataset["conn"]
            .execute(
                "SELECT id,password_hash FROM prototype.accounts WHERE username=%s",
                (new_username,),
            )
            .fetchone()
        )
        dataset["inserted"].append(("accounts", row[0]))
        assert row[1].startswith("$argon2id$")
        response = client.post(
            "/team/accounts/save",
            data={
                "_csrf": token,
                "_id": target["id"],
                "username": target["username"],
                "employee_id": target["employee_id"],
                "role": "manager",
                "active": "on",
                "password": "",
            },
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert (
            dataset["conn"]
            .execute(
                "SELECT COUNT(*) FROM prototype.sessions WHERE account_id=%s",
                (target["id"],),
            )
            .fetchone()[0]
            == 0
        )
