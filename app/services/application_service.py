from psycopg import AsyncConnection

from app.repositories.aplications import update_application_status
from app.repositories.client import create_client


async def register_aplication(conn: AsyncConnection, data):
    async with conn.transaction():
        if data.client_id is not None:
            client_id = data.client_id
        else:
            client_id = await create_client(
                conn,
                data.client.full_name,
                data.client.phone,
                data.client.email,
            )

        async with conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO applications
                    (client_id, employee_id, comment)
                VALUES (%s, %s, %s)
                RETURNING application_id
                """,
                (client_id, data.employee_id, data.comment),
            )

            application_id = (await cur.fetchone())[0]

            for item in data.items:
                await cur.execute(
                    """
                    INSERT INTO application_items
                        (application_id, nomenclature_id, program_id, quantity)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        application_id,
                        item.nomenclature_id,
                        item.program_id,
                        item.quantity,
                    ),
                )

    return {
        "client_id": client_id,
        "application_id": application_id,
        "items_count": len(data.items),
    }

async def change_application_status(
    conn: AsyncConnection,
    application_id: int,
    status: str,
):
    async with conn.transaction():
        return await update_application_status(
            conn,
            application_id,
            status,
        )