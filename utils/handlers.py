# user/handlers.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import async_session
from models import User
from user.keyboards import subscription_keyboard, phone_keyboard
from sqlalchemy import select
import os

router = Router()
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))

class UserState(StatesGroup):
    waiting_phone = State()

SOURCES = {
    "ice_arena": "Ice Arena", "bowling": "Bowling", "vr_arena": "VR Arena",
    "laser": "Laser Tag", "kids": "Kids Zone", "cafe": "Cafe", "main": "Asosiy kirish"
}

@router.message(CommandStart(deep_link=True))
async def start_cmd(message: Message, state: FSMContext, command=None):
    source = "Asosiy kirish"
    if command and command.args:
        key = command.args.lower().strip()
        source = SOURCES.get(key, key.replace("_", " ").title())
    await state.update_data(source=source)

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == message.from_user.id))
        if result.scalar_one_or_none():
            return await message.answer("Siz allaqachon ro‘yxatdan o‘tgansiz!\nFamilyParkda sizni kutamiz!")

    await message.answer(
        "FamilyParkga xush kelibsiz!\n\n"
        "Yangiliklardan boxabar bo‘lish uchun kanalga obuna bo‘ling:",
        reply_markup=subscription_keyboard()
    )

@router.callback_query(F.data == "check_subscription")
async def check_sub(call: CallbackQuery, state: FSMContext):
    member = await call.bot.get_chat_member(CHANNEL_ID, call.from_user.id)
    if member.status not in ("member", "administrator", "creator"):
        return await call.answer("Hali obuna bo‘lmadingiz!", show_alert=True)

    await call.message.edit_text("Telefon raqamingizni yuboring:", reply_markup=phone_keyboard())
    await state.set_state(UserState.waiting_phone)

@router.message(UserState.waiting_phone, F.contact)
async def save_contact(message: Message, state: FSMContext):
    data = await state.get_data()
    source = data.get("source", "Noma‘lum")
    user = message.from_user
    phone = message.contact.phone_number.replace("+", "").replace(" ", "")

    photos = await message.bot.get_user_profile_photos(user.id, limit=1)
    photo_id = photos.photos[0][-1].file_id if photos.total_count > 0 else None

    async with async_session() as session:
        new_user = User(
            telegram_id=user.id,
            first_name=user.first_name,
            username=user.username,
            phone=phone,
            source=source,
            profile_photo=photo_id
        )
        session.add(new_user)
        await session.commit()

    await message.answer(
        "Tabriklaymiz! Ro‘yxatdan o‘tdingiz!\n"
        "FamilyParkda sizni kutamiz!",
        reply_markup=None
    )
    await state.clear()