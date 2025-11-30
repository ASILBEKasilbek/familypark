# utils/admin_check.py
from database import async_session
from models import Admin
from sqlalchemy import select
from config import ADMIN_IDS


async def is_admin(user_id: int) -> bool:
    if user_id in ADMIN_IDS:
        return True
    async with async_session() as session:
        result = await session.execute(
            select(Admin.telegram_id).where(Admin.telegram_id == user_id)
        )
        return result.scalar_one_or_none() is not None

async def get_role(user_id: int) -> str:
    if user_id in ADMIN_IDS:
        return "superadmin"
    async with async_session() as session:
        result = await session.execute(
            select(Admin.role).where(Admin.telegram_id == user_id)
        )
        role = result.scalar_one_or_none()
        return role or "user"  # agar topilmasa "user" qaytaradi