from __future__ import annotations

from aiogram import Dispatcher

from app.bot.features import enabled_routers
from app.bot.middlewares import ErrorLoggingMiddleware, InteractionLoggingMiddleware


def create_dispatcher() -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.update.middleware(ErrorLoggingMiddleware())
    dispatcher.update.middleware(InteractionLoggingMiddleware())
    for router in enabled_routers():
        dispatcher.include_router(router)
    return dispatcher
