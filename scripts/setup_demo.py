"""Run from project root: python -m scripts.setup_demo [--seed]."""

import argparse

import psycopg
from psycopg import sql

from app.core.catalog import ENTITIES
from app.core.config import PROJECT_ROOT, get_settings


def main() -> None:
    parser = argparse.ArgumentParser(description="Подготовка локального прототипа")
    parser.add_argument(
        "--seed", action="store_true", help="Добавить вымышленные демоданные"
    )
    args = parser.parse_args()
    settings = get_settings()
    with (
        psycopg.connect(
            host=settings.db_host,
            port=settings.db_port,
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password.get_secret_value(),
        ) as conn,
        conn.transaction(),
    ):
        conn.execute(
            (PROJECT_ROOT / "database/migrations/001_prototype.sql").read_text(
                encoding="utf-8"
            )
        )
        conn.execute(
            (PROJECT_ROOT / "database/migrations/002_access.sql").read_text(
                encoding="utf-8"
            )
        )
        if args.seed:
            occupied = False
            for key in ENTITIES:
                row = conn.execute(
                    sql.SQL("SELECT EXISTS(SELECT 1 FROM {})").format(
                        sql.Identifier("prototype", key)
                    )
                ).fetchone()
                occupied = occupied or row[0]
            if occupied:
                print("Демоданные пропущены: в прототипе уже есть записи.")
            else:
                conn.execute(
                    (PROJECT_ROOT / "database/demo.sql").read_text(encoding="utf-8")
                )
                print("Вымышленные демоданные добавлены.")
    print("Таблицы прототипа готовы.")


if __name__ == "__main__":
    main()
