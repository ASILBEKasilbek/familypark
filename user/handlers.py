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
CHANNEL_ID = int(os.getenv("CHANNEL_ID", 0))  # .env da CHANNEL_ID borligiga ishonch hosil qiling

class UserStates(StatesGroup):
    waiting_phone = State()

# QR parametrlari
SOURCES_MAP = {
    "ice_arena": "Ice Arena",
    "bowling": "Bowling",
    "vr_arena": "VR Arena",
    "laser_tag": "Laser Tag",
    "kids_zone": "Kids Zone",
    "cafe": "Cafe",
    "main": "Asosiy kirish"
}

@router.message(CommandStart(deep_link=True))
async def cmd_start(message: Message, state: FSMContext, command=None):
    user = message.from_user
    source = "Asosiy kirish"

    # QR kod parametri
    if command and command.args:
        key = command.args.strip().lower()
        source = SOURCES_MAP.get(key, key.replace("_", " ").title())

    await state.update_data(source=source)

    # Bazada bor-yo‘qligini tekshirish
    async with async_session() as session:
        result = await session.execute(
            select(User.telegram_id).where(User.telegram_id == user.id)
        )
        if result.scalar_one_or_none():
            await message.answer(
                "Siz allaqachon ro‘yxatdan o‘tgansiz!\nFamilyParkda sizni kutamiz!"
            )
            return

    # Obuna so‘rash
    await message.answer(
        "Iltimos, FamilyPark News kanaliga obuna bo‘ling!\n\n"
        "Obuna bo‘lmasangiz, ro‘yxatdan o‘ta olmaysiz.",
        reply_markup=subscription_keyboard()
    )

@router.callback_query(F.data == "check_sub")
async def check_subscription(call: CallbackQuery, state: FSMContext):
    try:
        member = await call.bot.get_chat_member(CHANNEL_ID, call.from_user.id)
        if member.status not in ("member", "administrator", "creator"):
            await call.answer("Siz hali kanalga obuna bo‘lmadingiz!", show_alert=True)
            return
    except Exception:
        await call.answer("Obuna tekshirishda xatolik yuz berdi.", show_alert=True)
        return

    # ❌ edit_text bilan ReplyKeyboardMarkup ishlamaydi, shuning uchun answer ishlatamiz
    await call.message.answer(
        "Iltimos, telefon raqamingizni yuboring.",
        reply_markup=phone_keyboard()
    )
    await state.set_state(UserStates.waiting_phone)

@router.message(UserStates.waiting_phone, F.contact)
async def save_contact(message: Message, state: FSMContext):
    user = message.from_user
    phone = message.contact.phone_number.replace("+", "").replace(" ", "")
    data = await state.get_data()
    source = data.get("source", "Noma‘lum")

    # Profil rasm
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
        "Rahmat! Siz muvaffaqiyatli ro‘yxatdan o‘tdingiz.\n\n"
        "FamilyPark oilaviy dam olish markazida sizni kutamiz!",
        reply_markup=None  # oddiy matn, klaviatura yo'q
    )
    await state.clear()

# Boshqa xabarlar uchun
@router.message()
async def any_message(message: Message):
    # ❗ Agar cashier confirm modalini olgan bo‘lsa – bu handler ishlamasligi kerak
    if message.via_bot:
        return

    await message.answer(
        "Iltimos, /start buyrug‘ini bosing yoki QR orqali kirib keling."
    )
