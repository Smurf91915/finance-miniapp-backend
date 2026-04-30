import asyncio
import logging
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, MenuButtonCommands, MenuButtonWebApp, Update, WebAppInfo

from app.bot.api_client import BackendClient
from app.bot.handlers import router
from app.core.config import settings, telegram_webhook_url


BOT_COMMANDS = [
    BotCommand(command="start", description="Запустить бота и показать кнопки"),
    BotCommand(command="app", description="Открыть Mini App"),
    BotCommand(command="month", description="Показать сводку за месяц"),
    BotCommand(command="goals", description="Показать накопления и цели"),
]


class TelegramBotRuntime:
    def __init__(self) -> None:
        self.bot: Bot | None = None
        self.dispatcher: Dispatcher | None = None
        self.backend: BackendClient | None = None
        self._webhook_task: asyncio.Task[None] | None = None

    async def initialize(self) -> None:
        if self.bot and self.dispatcher and self.backend:
            return

        if not settings.bot_token:
            raise RuntimeError("BOT_TOKEN is not configured")

        session = AiohttpSession(proxy=settings.telegram_proxy) if settings.telegram_proxy else None
        self.bot = Bot(
            token=settings.bot_token,
            session=session,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
        )
        self.dispatcher = Dispatcher(storage=MemoryStorage())
        self.backend = BackendClient()
        self.dispatcher.include_router(router)
        self.dispatcher["backend"] = self.backend

    async def configure_for_polling(self) -> None:
        await self.initialize()
        assert self.bot is not None
        await self._configure_menu()
        # Polling and webhook cannot be active together.
        await self.bot.delete_webhook(drop_pending_updates=False)

    async def configure_for_webhook(self) -> None:
        await self.initialize()
        assert self.bot is not None
        assert self.dispatcher is not None

        webhook_url = telegram_webhook_url()
        if not webhook_url:
            raise RuntimeError("PUBLIC_BASE_URL is required when BOT_MODE=webhook")

        await self._configure_menu()
        await self.bot.set_webhook(
            webhook_url,
            allowed_updates=self.dispatcher.resolve_used_update_types(),
            drop_pending_updates=False,
            secret_token=settings.telegram_webhook_secret or None,
        )

    async def start_webhook_mode(self) -> None:
        if settings.bot_mode != "webhook":
            return

        await self.initialize()
        if self._webhook_task and not self._webhook_task.done():
            return
        self._webhook_task = asyncio.create_task(self._ensure_webhook_loop())

    async def handle_webhook_update(self, payload: dict[str, Any]) -> None:
        await self.initialize()
        assert self.bot is not None
        assert self.dispatcher is not None

        update = Update.model_validate(payload, context={"bot": self.bot})
        await self.dispatcher.feed_update(self.bot, update)

    async def shutdown(self) -> None:
        if self._webhook_task is not None:
            self._webhook_task.cancel()
            try:
                await self._webhook_task
            except asyncio.CancelledError:
                pass
            self._webhook_task = None

        if self.backend is not None:
            await self.backend.close()
            self.backend = None

        if self.bot is not None:
            await self.bot.session.close()
            self.bot = None

        self.dispatcher = None

    async def _configure_menu(self) -> None:
        assert self.bot is not None

        await self.bot.set_my_commands(BOT_COMMANDS)
        if settings.mini_app_url:
            await self.bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Открыть приложение",
                    web_app=WebAppInfo(url=settings.mini_app_url),
                )
            )
            return
        await self.bot.set_chat_menu_button(menu_button=MenuButtonCommands())

    async def _ensure_webhook_loop(self) -> None:
        while True:
            try:
                await self.configure_for_webhook()
                logging.info("Telegram webhook configured")
                return
            except TelegramNetworkError:
                logging.exception("Telegram API is unavailable, retrying webhook setup in 5 seconds")
            except Exception:
                logging.exception("Failed to configure Telegram webhook, retrying in 5 seconds")
            await asyncio.sleep(5)


runtime = TelegramBotRuntime()
