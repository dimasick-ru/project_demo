from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.pool import create_db_poll
from app.api.items import router as items_router

@asynccontextmanager
async def lifespan(app: FastAPI):

    pool = create_db_poll()
    await pool.open()
    app.state.db_pool = pool
    print("база данных подключена")

    yield

    await pool.close()
    print("база данных отключена")

app = FastAPI(lifespan=lifespan)

app = FastAPI(
    title="Магазин",
    description="API для магазина тест",
    lifespan=lifespan,
    docs_url="/docs"
)

app.include_router(items_router)

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "API is healthy"}