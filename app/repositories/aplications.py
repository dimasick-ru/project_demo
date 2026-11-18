from psycopg import AsyncConnection
from psycopg.rows import dict_row


async def get_aplications(
    conn: AsyncConnection,
    limit: int = 50,
    offset: int = 0,
):

    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT
                a.application_id,
                a.client_id,
                c.full_name AS client_name,
                a.employee_id,
                a.created_at,
                a.status,
                a.comment,
                COUNT(ai.application_item_id)::int AS items_count
            FROM applications AS a
            JOIN clients AS c ON c.client_id = a.client_id
            LEFT JOIN application_items AS ai
                ON ai.application_id = a.application_id
            GROUP BY a.application_id, c.full_name
            ORDER BY a.created_at DESC, a.application_id DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        )
        return await cur.fetchall()
    
async def get_aplication(
        conn: AsyncConnection,
        application_id: int,
):
    async with conn.cursor(row_factory=dict_row) as cur:
        await cur.execute(
            """
            SELECT
                a.application_id,
                a.client_id,
                c.full_name AS client_name,
                c.phone AS client_phone,
                c.email AS client_email,
                a.employee_id,
                a.created_at,
                a.status,
                a.comment
            FROM applications AS a
            JOIN clients AS c ON c.client_id = a.client_id
            WHERE a.application_id = %s
            """,
            (application_id,),
        )
        application = await cur.fetchone()

        if application is None:
            return None

            
        await cur.execute(
            """
            SELECT
                ai.application_item_id,
                ai.nomenclature_id,
                ai.program_id,
                COALESCE(n.name, p.name) AS name,
                ai.quantity
            FROM application_items AS ai
            LEFT JOIN nomenclature AS n
                ON n.nomenclature_id = ai.nomenclature_id
            LEFT JOIN programs AS p
                ON p.program_id = ai.program_id
            WHERE ai.application_id = %s
            ORDER BY ai.application_item_id
            """,
            (application_id,),
        )
        application["items"] = await cur.fetchall()

        return application

async def update_application_status(
    conn: AsyncConnection,
    application_id: int,
    status: str,
):
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                UPDATE applications
                SET status = %s
                WHERE application_id = %s
                RETURNING application_id, status
                """,
                (status, application_id),
            )
            return await cur.fetchone()