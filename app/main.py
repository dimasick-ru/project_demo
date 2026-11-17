from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.items import router as items_router
from app.db.pool import create_db_poll
from app.api.applications import router as applications_router


@asynccontextmanager
async def lifespan(app: FastAPI):

    pool = create_db_poll()
    await pool.open()
    app.state.db_pool = pool
    print("база данных подключена")

    yield

    await pool.close()
    print("база данных отключена")

app = FastAPI(
    title="Магазин",
    description="API для магазина тест",
    lifespan=lifespan,
    docs_url="/docs"
)

app.include_router(items_router)
app.include_router(applications_router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "Сервис работает"}

@app.get("/health/db")
async def database_health():
    async with app.state.db_pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
            result = await cur.fetchone()

    return {"database": "ok" if result[0] == 1 else "error"}