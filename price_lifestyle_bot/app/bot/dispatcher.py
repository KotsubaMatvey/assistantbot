from __future__ import annotations

from aiogram import Dispatcher

from app.bot.features import enabled_routers
from app.bot.middlewares import (
    AccessControlMiddleware,
    ErrorLoggingMiddleware,
    InteractionLoggingMiddleware,
)


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.update.middleware(ErrorLoggingMiddleware())
    dispatcher.update.middleware(AccessControlMiddleware())
    dispatcher.update.middleware(InteractionLoggingMiddleware())
    for router in enabled_routers():
        dispatcher.include_router(router)
    return dispatcher
