from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Basket, BasketItem
from app.services.basket_parser import BasketItemParsed


async def create_basket(
    session: AsyncSession,
    *,
    user_id: int,
    raw_text: str,
    items: list[BasketItemParsed],
) -> Basket:
    basket = Basket(user_id=user_id, raw_text=raw_text)
    session.add(basket)
    await session.flush()
    for item in items:
        session.add(
            BasketItem(
                basket_id=basket.id,
                raw_text=item.raw_text,
                parsed_name=item.name,
                desired_quantity_value=item.quantity_value,
                desired_quantity_unit=item.quantity_unit,
            )
        )
    await session.flush()
    return basket


async def get_latest_basket_for_user(session: AsyncSession, user_id: int) -> Basket | None:
    result = await session.execute(
        select(Basket).where(Basket.user_id == user_id).order_by(desc(Basket.created_at)).limit(1)
    )
    return result.scalar_one_or_none()
