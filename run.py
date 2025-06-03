import logging
import asyncio
from settings import dp
from database import init_db
import handler  # Импортируем файл с хендлерами

logging.basicConfig(level=logging.INFO)

async def main():
    await init_db()
    handler.register_handlers(dp)   # <-- Важно! Вызвать регистрацию здесь
    print("Бот запущен")
    await dp.start_polling()

if __name__ == "__main__":
    asyncio.run(main())
