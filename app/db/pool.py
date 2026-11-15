from psycopg.conninfo import make_conninfo
from psycopg_pool import AsyncConnectionPool

from app.core.config import get_settings


def create_db_poll() -> AsyncConnectionPool:
    settings = get_settings()

    conninfo = make_conninfo(
        host=settings.db_host,
        port=settings.db_port,
        dbname=settings.db_name,
        user=settings.db_user,
        password=settings.db_password.get_secret_value(),
        connect_timeout=5
    )
    return AsyncConnectionPool(
        conninfo=conninfo,
        min_size=0,
        max_size=5,
        timeout=5,
        open=False
    )
