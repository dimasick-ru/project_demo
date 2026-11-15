from psycopg_pool import AsyncConnectionPool

async def get_all_items(poll: AsyncConnectionPool):
    async with poll.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM items")
            rows = await cur.fetchall()



            return [
                {"id": row[0], "name": row[1], "price": float(row[2])} 
                for row in rows
            ]
            
async def create_item(pool: AsyncConnectionPool, name: str, price: float) -> dict:
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO items (name, price) VALUES (%s, %s) RETURNING id, name, price",
                (name, price)   
            )
            row = await cur.fetchone()
            return {"id": row[0], "name": row[1], "price": float(row[2])}
            