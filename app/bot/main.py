import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, MenuButtonCommands, MenuButtonWebApp, WebAppInfo

from app.bot.api_client import BackendClient
from app.bot.handlers import router
from app.core.config import settings


BOT_COMMANDS = [
    BotCommand(command="start", description="Запустить бота и показать кнопки"),
    BotCommand(command="app", description="Открыть Mini App"),
    BotCommand(command="month", description="Показать сводку за месяц"),
    BotCommand(command="goals", description="Показать накопления и цели"),
]


async def configure_bot(bot: Bot) -> None:
    # Polling and webhook cannot be active together.
    await bot.delete_webhook(drop_pending_updates=False)
    await bot.set_my_commands(BOT_COMMANDS)
    if settings.mini_app_url:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Открыть приложение",
                web_app=WebAppInfo(url=settings.mini_app_url),
            )
        )
        return
    await bot.set_chat_menu_button(menu_button=MenuButtonCommands())


async def main() -> None:
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is not configured in .env")

    logging.basicConfig(level=logging.INFO)

    session = AiohttpSession(proxy=settings.telegram_proxy) if settings.telegram_proxy else None
    bot = Bot(
        token=settings.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dispatcher = Dispatcher(storage=MemoryStorage())
    backend = BackendClient()

    dispatcher.include_router(router)
    dispatcher["backend"] = backend

    try:
        while True:
            try:
                await configure_bot(bot)
                await dispatcher.start_polling(bot)
                break
            except TelegramNetworkError:
                logging.exception("Telegram API is unavailable, retrying bot polling in 5 seconds")
                await asyncio.sleep(5)
    finally:
        await backend.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
