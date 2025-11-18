# main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
import os

from database import engine, Base
from user.handlers import router as user_router
from admin.handlers import router as admin_router  # agar admin tayyor bo‘lsa
from aiogram.client.default import DefaultBotProperties


load_dotenv()
logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=os.getenv("BOT_TOKEN"),
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def main():
    await create_tables()

    dp.include_router(admin_router)
    dp.include_router(user_router)  # keyinroq qo‘shasiz
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())