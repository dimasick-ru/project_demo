import hashlib
import secrets
from typing import Any

from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.access import User

COOKIE = "rd_session"


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def account_for_login(pool: AsyncConnectionPool, username: str) -> dict | None:
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            "SELECT * FROM prototype.accounts WHERE username = %s", (username,)
        )
        return await cur.fetchone()


async def resolve_session(pool: AsyncConnectionPool, token: str) -> User | None:
    if not token or len(token) > 200:
        return None
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT a.id, a.employee_id, a.username, e.name, a.role, s.csrf_token
            FROM prototype.sessions s JOIN prototype.accounts a ON a.id=s.account_id
            JOIN prototype.employees e ON e.id=a.employee_id
            WHERE s.token_hash=%s AND s.expires_at > CURRENT_TIMESTAMP AND a.active
        """,
            (token_hash(token),),
        )
        row = await cur.fetchone()
        return User(**row) if row else None


async def create_session(pool: AsyncConnectionPool, account_id: int) -> str:
    token = secrets.token_urlsafe(32)
    async with pool.connection() as conn, conn.transaction():
        await conn.execute(
            "DELETE FROM prototype.sessions WHERE expires_at <= CURRENT_TIMESTAMP"
        )
        await conn.execute(
            """INSERT INTO prototype.sessions (token_hash,account_id,csrf_token,expires_at)
            VALUES (%s,%s,%s,CURRENT_TIMESTAMP + INTERVAL '8 hours')""",
            (token_hash(token), account_id, secrets.token_urlsafe(32)),
        )
    return token


async def delete_session(pool: AsyncConnectionPool, token: str) -> None:
    async with pool.connection() as conn:
        await conn.execute(
            "DELETE FROM prototype.sessions WHERE token_hash=%s", (token_hash(token),)
        )


async def employee_options(pool: AsyncConnectionPool, user: User) -> dict[int, str]:
    async with pool.connection() as conn, conn.cursor() as cur:
        if user.role == "manager":
            await cur.execute(
                "SELECT id,name FROM prototype.employees WHERE id=%s",
                (user.employee_id,),
            )
        else:
            await cur.execute("SELECT id,name FROM prototype.employees ORDER BY name")
        return dict(await cur.fetchall())


async def manager_options(pool: AsyncConnectionPool) -> dict[int, str]:
    async with pool.connection() as conn, conn.cursor() as cur:
        await cur.execute("""SELECT e.id,e.name || CASE WHEN a.active THEN '' ELSE ' (вход отключён)' END
            FROM prototype.employees e
            JOIN prototype.accounts a ON a.employee_id=e.id
            WHERE a.role='manager' ORDER BY e.name""")
        return dict(await cur.fetchall())


async def list_accounts(pool: AsyncConnectionPool) -> list[dict[str, Any]]:
    async with pool.connection() as conn, conn.cursor(row_factory=dict_row) as cur:
        await cur.execute("""SELECT a.id,a.employee_id,a.username,a.role,a.active,e.name
            FROM prototype.accounts a JOIN prototype.employees e ON e.id=a.employee_id
            ORDER BY a.id""")
        return await cur.fetchall()


async def save_account(
    pool: AsyncConnectionPool, values: dict, account_id: int | None
) -> int:
    async with (
        pool.connection() as conn,
        conn.transaction(),
        conn.cursor(row_factory=dict_row) as cur,
    ):
        # Serialize role edits so concurrent requests cannot remove the last director.
        await cur.execute("LOCK TABLE prototype.accounts IN SHARE ROW EXCLUSIVE MODE")
        if account_id:
            await cur.execute(
                "SELECT role,active FROM prototype.accounts WHERE id=%s", (account_id,)
            )
            old = await cur.fetchone()
            if not old:
                raise ValueError("Учётная запись не найдена")
            if (
                old["role"] == "director"
                and old["active"]
                and (values["role"] != "director" or not values["active"])
            ):
                await cur.execute(
                    "SELECT COUNT(*) AS count FROM prototype.accounts WHERE role='director' AND active"
                )
                if (await cur.fetchone())["count"] <= 1:
                    raise ValueError(
                        "Нельзя отключить или понизить роль последнего руководителя"
                    )
            await cur.execute(
                """UPDATE prototype.accounts SET username=%s,employee_id=%s,role=%s,
                active=%s,password_hash=COALESCE(%s,password_hash) WHERE id=%s RETURNING id""",
                (
                    values["username"],
                    values["employee_id"],
                    values["role"],
                    values["active"],
                    values.get("password_hash"),
                    account_id,
                ),
            )
            await cur.execute(
                "DELETE FROM prototype.sessions WHERE account_id=%s", (account_id,)
            )
        else:
            await cur.execute(
                """INSERT INTO prototype.accounts
                (username,employee_id,role,active,password_hash) VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                (
                    values["username"],
                    values["employee_id"],
                    values["role"],
                    values["active"],
                    values["password_hash"],
                ),
            )
            account_id = (await cur.fetchone())["id"]
        return account_id
