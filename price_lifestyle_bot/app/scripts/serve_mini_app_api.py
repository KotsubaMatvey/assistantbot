from __future__ import annotations

import asyncio

from app.config import get_settings
from app.logging_config import configure_logging
from app.services.mini_app_server import MiniAppHttpServer


async def main() -> None:
    configure_logging()
    server = MiniAppHttpServer(get_settings())
    await server.start()
    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
