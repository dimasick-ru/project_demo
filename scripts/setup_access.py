"""Apply access migration and create initial accounts without storing plaintext passwords."""

import argparse
import getpass
import secrets

import psycopg
from pwdlib import PasswordHash

from app.core.config import PROJECT_ROOT, get_settings

passwords = PasswordHash.recommended()


def add_account(conn, username: str, name: str, role: str, password: str) -> bool:
    if conn.execute(
        "SELECT id FROM prototype.accounts WHERE username=%s", (username,)
    ).fetchone():
        return False
    employee = conn.execute(
        "SELECT id FROM prototype.employees WHERE name=%s ORDER BY id LIMIT 1", (name,)
    ).fetchone()
    if employee is None:
        employee = conn.execute(
            "INSERT INTO prototype.employees (name,role,status) VALUES (%s,%s,%s) RETURNING id",
            (name, role, "Работает"),
        ).fetchone()
    conn.execute(
        """INSERT INTO prototype.accounts (employee_id,username,password_hash,role)
        VALUES (%s,%s,%s,%s)""",
        (employee[0], username, passwords.hash(password), role),
    )
    return True


def seed_owners(conn) -> None:
    # Assign ONLY known fictional demo rows. Existing assignments are preserved.
    for username, names in {
        "manager1": [
            "Виктор Павлович Озеров",
            "Елена Сергеевна Светлова",
            "Наталья Олеговна Соснова",
        ],
        "manager2": ["Марина Александровна Лесная", "Андрей Игоревич Мирный"],
    }.items():
        conn.execute(
            """UPDATE prototype.clients SET owner_employee_id=(
            SELECT employee_id FROM prototype.accounts WHERE username=%s)
            WHERE owner_employee_id IS NULL AND name=ANY(%s)
            AND (contact LIKE '+7 (000) %%' OR contact IN ('elena@example.com','andrey@example.com'))""",
            (username, names),
        )
    for username, names in {
        "manager1": ["Ознакомительное занятие"],
        "manager2": ["Индивидуальное занятие", "Набор для домашних занятий"],
    }.items():
        conn.execute(
            """UPDATE prototype.nomenclature SET owner_employee_id=(
            SELECT employee_id FROM prototype.accounts WHERE username=%s)
            WHERE owner_employee_id IS NULL AND name=ANY(%s)""",
            (username, names),
        )
    conn.execute("""UPDATE prototype.payments SET owner_employee_id=(
        SELECT employee_id FROM prototype.accounts WHERE username='manager2')
        WHERE owner_employee_id IS NULL AND (receipt_number,basis) IN
        (('Ч-001','Продажа П-001'),('Ч-002','Договор Д-001'))""")


def main() -> None:
    parser = argparse.ArgumentParser(description="Создание доступа сотрудников")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Создать четыре демонстрационные учётные записи",
    )
    parser.add_argument("--username")
    parser.add_argument("--employee-id", type=int)
    parser.add_argument(
        "--role", choices=["manager", "administrator", "director"], default="director"
    )
    args = parser.parse_args()
    if not args.demo and (not args.username or not args.employee_id):
        parser.error("Укажите --demo либо --username и --employee-id")
    settings = get_settings()
    credentials = []
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
        for name in ("001_prototype.sql", "002_access.sql"):
            conn.execute(
                (PROJECT_ROOT / "database/migrations" / name).read_text(
                    encoding="utf-8"
                )
            )
        if args.demo:
            for username, name, role in (
                ("manager1", "Ольга Викторовна Речная", "manager"),
                ("manager2", "Алексей Сергеевич Луговой", "manager"),
                ("admin", "Ирина Петровна Полевая", "administrator"),
                ("director", "Софья Андреевна Ясная", "director"),
            ):
                password = secrets.token_urlsafe(12)
                if add_account(conn, username, name, role, password):
                    credentials.append((username, password))
            seed_owners(conn)
        else:
            from app.services.auth import AccountInput

            values = AccountInput(
                username=args.username.strip().lower(),
                employee_id=args.employee_id,
                role=args.role,
                active=True,
            )
            if not conn.execute(
                "SELECT id FROM prototype.employees WHERE id=%s",
                (values.employee_id,),
            ).fetchone():
                raise ValueError("Сотрудник не найден")
            password = getpass.getpass("Password (10+ characters): ")
            if len(password) < 10 or password != getpass.getpass("Confirm password: "):
                raise ValueError(
                    "Пароли должны совпадать и содержать не менее 10 символов"
                )
            conn.execute(
                """INSERT INTO prototype.accounts (employee_id,username,password_hash,role)
                    VALUES (%s,%s,%s,%s)""",
                (
                    values.employee_id,
                    values.username,
                    passwords.hash(password),
                    values.role,
                ),
            )
    for username, password in credentials:
        print(f"{username}: {password}")
    print("Access setup complete. Existing accounts/passwords were not changed.")


if __name__ == "__main__":
    main()
