from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from psycopg import Error as DatabaseError
from psycopg_pool import PoolTimeout

from app.api.items import router as items_router
from app.core.config import PROJECT_ROOT
from app.db.pool import create_db_poll
from app.web.routes import database_error
from app.web.routes import router as web_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:

    pool = create_db_poll()
    await pool.open()
    app.state.db_pool = pool
    try:
        yield
    finally:
        await pool.close()


app = FastAPI(
    title="Рецепты долголетия",
    description="Прототип системы управления центром",
    lifespan=lifespan,
    docs_url="/docs",
)

app.include_router(items_router)
app.include_router(web_router)
app.mount(
    "/static", StaticFiles(directory=PROJECT_ROOT / "app/web/static"), name="static"
)
app.add_exception_handler(DatabaseError, database_error)
app.add_exception_handler(PoolTimeout, database_error)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "message": "Сервис работает"}
