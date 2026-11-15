from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.repositories.items import create_item as create_item_repo
from app.repositories.items import get_all_items

router = APIRouter(prefix="/items", tags=["Товары"])

class ItemCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100, description="Название товара")
    price: float = Field(gt=0, description="Цена товара")

@router.get("")
async def get_items(request: Request) -> list[dict]:
    pool = request.app.state.db_pool

    items = await get_all_items(pool)

    return items

@router.post("")
async def create_item(item: ItemCreate, request: Request) -> dict:

    pool = request.app.state.db_pool

    new_item = await create_item_repo(pool, item.name, item.price)

    return new_item

