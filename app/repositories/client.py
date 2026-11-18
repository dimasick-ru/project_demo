from psycopg import AsyncConnection


async def create_client(
    conn: AsyncConnection,
    full_name: str,
    phone: str | None,
    email: str | None,
) -> int:
    async with conn.cursor() as cur:
        await cur.execute(
            """
            INSERT INTO clients (full_name, phone, email)
            VALUES (%s, %s, %s)
            RETURNING client_id
            """,
            (full_name, phone, email),
        )
        row = await cur.fetchone()
        return row[0]