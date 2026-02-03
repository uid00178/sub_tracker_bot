import asyncio
from aiohttp import web

import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand

from app.config import load_config
from app.handlers import setup as setup_handlers

cfg = load_config()


async def setup_bot_commands(bot: Bot):
    # Команды, которые Telegram показывает в списке команд бота
    await bot.set_my_commands([
        BotCommand(command="start", description="Открыть меню"),
        BotCommand(command="add", description="Добавить подписку"),
        BotCommand(command="list", description="Все мои подписки"),
        BotCommand(command="help", description="Помощь"),
    ])


async def run_polling(bot: Bot, dp: Dispatcher):
    await dp.start_polling(bot)


async def run_webhook(bot: Bot, dp: Dispatcher):
    if not cfg.webhook_base or not cfg.webhook_secret:
        raise RuntimeError("Для webhook нужны WEBHOOK_BASE и WEBHOOK_SECRET в .env")

    app = web.Application()

    async def handle_update(request: web.Request):
        secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if secret != cfg.webhook_secret:
            return web.Response(status=403, text="forbidden")

        data = await request.json()
        update = dp.update.model_validate(data)
        await dp.feed_update(bot, update)
        return web.Response(text="ok")

    app.router.add_post(cfg.webhook_path, handle_update)

    url = cfg.webhook_base.rstrip("/") + cfg.webhook_path
    await bot.set_webhook(
        url=url,
        secret_token=cfg.webhook_secret,
        drop_pending_updates=False,
    )

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, cfg.web_server_host, cfg.web_server_port)
    await site.start()

    # держим процесс живым
    while True:
        await asyncio.sleep(3600)


async def main():
    bot = Bot(token=cfg.bot_token)
    dp = Dispatcher()
    setup_handlers(dp)

    # ВАЖНО: команды выставляем до старта polling/webhook
    await setup_bot_commands(bot)

    if cfg.mode == "webhook":
        await run_webhook(bot, dp)
    else:
        await run_polling(bot, dp)


if __name__ == "__main__":
    asyncio.run(main())
