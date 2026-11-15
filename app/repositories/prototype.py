from typing import Any

from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from app.core.access import OWNED, PARENTS, User, require_access
from app.core.catalog import ENTITIES


def table(key: str) -> sql.Identifier:
    # Only names from the server-owned catalog can reach SQL identifiers.
    if key not in ENTITIES:
        raise ValueError("Unknown entity")
    return sql.Identifier("prototype", key)


def scope(key: str, user: User) -> tuple[sql.Composable, list[int]]:
    if user.role != "manager" or key not in OWNED:
        return sql.SQL("TRUE"), []
    if key in PARENTS:
        column, parent = PARENTS[key]
        return (
            sql.SQL("""(EXISTS (SELECT 1 FROM {} parent WHERE parent.id=r.{}
            AND parent.owner_employee_id=%s) OR (r.{} IS NULL AND r.owner_employee_id=%s))""").format(
                table(parent), sql.Identifier(column), sql.Identifier(column)
            ),
            [user.employee_id] * 2,
        )
    return sql.SQL("r.owner_employee_id=%s"), [user.employee_id]


async def list_records(
    pool: AsyncConnectionPool, key: str, user: User
) -> list[dict[str, Any]]:
    require_access(user, key)
    condition, params = scope(key, user)
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            sql.SQL("SELECT r.* FROM {} r WHERE {} ORDER BY r.id DESC").format(
                table(key), condition
            ),
            params,
        )
        return await cur.fetchall()


async def get_record(
    pool: AsyncConnectionPool, key: str, record_id: int, user: User
) -> dict | None:
    require_access(user, key)
    condition, params = scope(key, user)
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            sql.SQL("SELECT r.* FROM {} r WHERE r.id = %s AND {}").format(
                table(key), condition
            ),
            [record_id, *params],
        )
        return await cur.fetchone()


async def save_record(
    pool: AsyncConnectionPool,
    key: str,
    values: dict,
    user: User,
    record_id: int | None = None,
) -> int | None:
    require_access(user, key, write=True)
    entity = ENTITIES[key]
    columns = [sql.Identifier(field.key) for field in entity.fields]
    params = [
        Jsonb(values[field.key]) if field.kind == "json" else values[field.key]
        for field in entity.fields
    ]
    if key in OWNED:
        columns.append(sql.Identifier("owner_employee_id"))
        params.append(
            user.employee_id
            if user.role == "manager"
            else values.get("owner_employee_id")
        )
    if record_id is None:
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
            table(key),
            sql.SQL(", ").join(columns),
            sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )
    else:
        condition, scope_params = scope(key, user)
        query = sql.SQL(
            "UPDATE {} AS r SET {} WHERE r.id = %s AND {} RETURNING r.id"
        ).format(
            table(key),
            sql.SQL(", ").join(sql.SQL("{} = %s").format(column) for column in columns),
            condition,
        )
        params.append(record_id)
        params.extend(scope_params)
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query, params)
        row = await cur.fetchone()
        return row[0] if row else None
