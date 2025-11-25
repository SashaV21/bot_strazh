import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage  # <-- добавлено
import core.config as config  # исправлен импорт

from handlers.all_handlers import router
from core.database import init_db

async def main():
    await init_db()
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher(storage=MemoryStorage())  # <-- добавлено storage

    dp.include_router(router)

    try:
        print("Бот запущен. Ctrl+C для остановки")
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        print("\nОстанавливаю")
    finally:
        await bot.session.close()
        print("Бот остановлен")

if __name__ == "__main__":
    asyncio.run(main())