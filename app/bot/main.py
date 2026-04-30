import asyncio
import logging

from aiogram.exceptions import TelegramNetworkError

from app.bot.runtime import runtime
from app.core.config import settings


async def main() -> None:
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is not configured in .env")
    if settings.bot_mode == "webhook":
        raise RuntimeError("BOT_MODE=webhook requires running `uvicorn app.main:app`, not `python -m app.bot.main`.")

    logging.basicConfig(level=logging.INFO)

    try:
        while True:
            try:
                await runtime.configure_for_polling()
                assert runtime.bot is not None
                assert runtime.dispatcher is not None
                await runtime.dispatcher.start_polling(runtime.bot)
                break
            except TelegramNetworkError:
                logging.exception("Telegram API is unavailable, retrying bot polling in 5 seconds")
                await asyncio.sleep(5)
    finally:
        await runtime.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
