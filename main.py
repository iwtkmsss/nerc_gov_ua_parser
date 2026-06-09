import sys
import logging
import asyncio
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.fsm.storage.memory import MemoryStorage

from handlers.user import bot_callback, bot_messages, start_command
from handlers.admin import command
from misc import TOKEN, BDB, BASE_DIR, parse
from misc.util import format_changes_message


CHECK_INTERVAL_SECONDS = int(os.getenv("CHECK_INTERVAL_SECONDS", "3600"))
MONITORING_START_HOUR = int(os.getenv("MONITORING_START_HOUR", "9"))
MONITORING_END_HOUR = int(os.getenv("MONITORING_END_HOUR", "18"))
MESSAGE_SAFE_LIMIT = 3900


def setup_logging():
    logs_dir = BASE_DIR / "logs"
    logs_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s:%(name)s:%(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            RotatingFileHandler(
                logs_dir / "bot.log",
                maxBytes=1_000_000,
                backupCount=3,
                encoding="utf-8"
            ),
        ],
    )


def split_message(text, limit=MESSAGE_SAFE_LIMIT):
    if len(text) <= limit:
        return [text]

    chunks = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(line) > limit:
            if current:
                chunks.append(current.rstrip())
                current = ""
            chunks.extend(line[i:i + limit] for i in range(0, len(line), limit))
            continue

        if len(current) + len(line) > limit:
            chunks.append(current.rstrip())
            current = line
        else:
            current += line

    if current:
        chunks.append(current.rstrip())

    return chunks


def is_monitoring_time(now=None):
    now = now or datetime.now()
    if MONITORING_START_HOUR == MONITORING_END_HOUR:
        return True

    if MONITORING_START_HOUR < MONITORING_END_HOUR:
        return MONITORING_START_HOUR <= now.hour < MONITORING_END_HOUR

    return now.hour >= MONITORING_START_HOUR or now.hour < MONITORING_END_HOUR


async def send_changes(bot, users, changes):
    if not changes:
        return

    messages = split_message(format_changes_message(changes))

    for user in users:
        for message in messages:
            try:
                await bot.send_message(user["tg_id"], message, disable_web_page_preview=True)
            except TelegramForbiddenError:
                BDB.unsubscribe_user(user["tg_id"])
                logging.info("User %s blocked the bot, subscription disabled", user["tg_id"])
                break
            except TelegramBadRequest:
                logging.exception("Unable to send monitoring message to %s", user["tg_id"])
                break


async def monitoring_loop(bot):
    await asyncio.sleep(5)
    while True:
        try:
            if not is_monitoring_time():
                logging.info(
                    "Monitoring skipped: outside active hours %s:00-%s:00",
                    MONITORING_START_HOUR,
                    MONITORING_END_HOUR
                )
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                continue

            users = BDB.get_subscribed_users()
            if not users:
                logging.info("Monitoring skipped: no subscribers")
                await asyncio.sleep(CHECK_INTERVAL_SECONDS)
                continue

            changes = await asyncio.to_thread(parse)
            BDB.record_check(len(changes))
            await send_changes(bot, users, changes)
            logging.info("Monitoring check finished, changes: %s", len(changes))
        except Exception:
            logging.exception("Monitoring check failed")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


async def main():
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='HTML'))
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_routers(
        start_command.router,
        command.router,
        bot_callback.router,
        bot_messages.router
    )

    await bot.delete_webhook(drop_pending_updates=True)
    monitor_task = asyncio.create_task(monitoring_loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        monitor_task.cancel()
        await bot.session.close()


if __name__ == '__main__':
    print("[+] BOT STARTING")
    setup_logging()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("[-] BOT HAS BEEN DISABLE")
        BDB.close()
