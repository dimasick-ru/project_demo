import secrets
from typing import Literal

from psycopg_pool import AsyncConnectionPool
from pwdlib import PasswordHash
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.repositories import auth as repository

passwords = PasswordHash.recommended()
# One process-local dummy hash prevents the nonexistent-user fast path.
_dummy = passwords.hash(secrets.token_urlsafe(32))


class AccountInput(BaseModel):
    username: str = Field(pattern=r"^[a-z0-9._-]{3,64}$")
    employee_id: int = Field(gt=0)
    role: Literal["manager", "administrator", "director"]
    active: bool


async def login(pool: AsyncConnectionPool, username: str, password: str) -> str | None:
    account = await repository.account_for_login(pool, username.strip().lower())
    valid = await run_in_threadpool(
        passwords.verify, password, account["password_hash"] if account else _dummy
    )
    if not account or not valid or not account["active"]:
        return None
    return await repository.create_session(pool, account["id"])
