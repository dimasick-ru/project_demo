from typing import Any

from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from app.core.catalog import ENTITIES


def table(key: str) -> sql.Identifier:
    # Only names from the server-owned catalog can reach SQL identifiers.
    if key not in ENTITIES:
        raise ValueError("Unknown entity")
    return sql.Identifier("prototype", key)


async def list_records(pool: AsyncConnectionPool, key: str) -> list[dict[str, Any]]:
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            sql.SQL("SELECT * FROM {} ORDER BY id DESC").format(table(key))
        )
        return await cur.fetchall()


async def get_record(
    pool: AsyncConnectionPool, key: str, record_id: int
) -> dict | None:
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            sql.SQL("SELECT * FROM {} WHERE id = %s").format(table(key)), (record_id,)
        )
        return await cur.fetchone()


async def save_record(
    pool: AsyncConnectionPool, key: str, values: dict, record_id: int | None = None
) -> int | None:
    entity = ENTITIES[key]
    columns = [sql.Identifier(field.key) for field in entity.fields]
    params = [
        Jsonb(values[field.key]) if field.kind == "json" else values[field.key]
        for field in entity.fields
    ]
    if record_id is None:
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING id").format(
            table(key),
            sql.SQL(", ").join(columns),
            sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )
    else:
        query = sql.SQL("UPDATE {} SET {} WHERE id = %s RETURNING id").format(
            table(key),
            sql.SQL(", ").join(sql.SQL("{} = %s").format(column) for column in columns),
        )
        params.append(record_id)
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute(query, params)
        row = await cur.fetchone()
        return row[0] if row else None
