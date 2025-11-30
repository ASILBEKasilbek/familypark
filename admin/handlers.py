# admin/handlers.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import async_session
from models import User, Admin,QRLog,AttendanceLog
from utils.admin_check import is_admin, get_role
from utils.misc import generate_qr, create_excel,export_attendance_excel
from admin.keyboards import admin_main_keyboard, back_button, admin_list_keyboard
from sqlalchemy import select, func, delete
from datetime import datetime, date
import os
import asyncio
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
router = Router()

# States
class AdminStates(StatesGroup):
    broadcast = State()
    qr_key = State()
    cashier_search = State()

class SuperAdminStates(StatesGroup):
    waiting_admin_id = State()
    waiting_admin_role = State()
    waiting_remove_admin = State()


# ====================== ADMIN PANEL KIRISH ======================
@router.message(F.text == "/admin")
async def admin_panel(message: Message):
    if not await is_admin(message.from_user.id):
        return await message.answer("Siz admin emassiz!")

    role = await get_role(message.from_user.id)
    text = f"Admin panel\n\nRolingiz: <b>{role.upper()}</b>"

    await message.answer(
        text,
        reply_markup=admin_main_keyboard(role)
    )


# ====================== STATISTIKA ======================
@router.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    today = date.today()
    async with async_session() as session:
        total = await session.scalar(select(func.count(User.id)))
        today_count = await session.scalar(
            select(func.count(User.id)).where(func.date(User.attended_date) == today)
        )
        sources_result = await session.execute(
            select(User.source, func.count(User.id))
            .group_by(User.source)
        )
        sources = sources_result.all()

    text = f"<b>Foydalanuvchi statistikasi</b>\n\n" \
           f"Jami foydalanuvchilar: <b>{total}</b>\n" \
           f"Bugun kelganlar: <b>{today_count}</b>\n\n" \
           f"Manbalar bo'yicha:\n"

    if sources:
        for src, cnt in sources:
            src_name = src if src else "Noma'lum"
            text += f"└ {src_name}: {cnt}\n"
    else:
        text += "└ Ma'lumot yo'q"

    await call.message.edit_text(text, reply_markup=back_button())


# ====================== EXCEL EXPORT ======================
@router.callback_query(F.data == "admin_export")
async def admin_export(call: CallbackQuery):
    role = await get_role(call.from_user.id)
    if role not in ("admin", "superadmin"):
        return await call.answer("Sizda ruxsat yo'q!", show_alert=True)

    async with async_session() as session:
        users = await session.execute(select(User))
        users = users.scalars().all()

    file_path = create_excel(
        users,
        headers=["ID", "Telegram ID", "Ism", "Username", "Telefon", "Source", "Ro'yxatdan o'tgan"]
    )

    await call.message.delete()
    await call.message.answer_document(
        FSInputFile(file_path),
        caption=f"Foydalanuvchilar soni: {len(users)}"
    )
    os.remove(file_path)

@router.callback_query(F.data == "admin_export_2")
async def admin_export(call: CallbackQuery):
    role = await get_role(call.from_user.id)
    if role not in ("admin", "superadmin"):
        return await call.answer("Sizda ruxsat yo'q!", show_alert=True)

    file_path = await export_attendance_excel(async_session)

    await call.message.delete()
    await call.message.answer_document(
        FSInputFile(file_path),
        caption="Attendance ro'yxati"
    )
    os.remove(file_path)


# ====================== BROADCAST (SMM + SuperAdmin) ======================
@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    role = await get_role(call.from_user.id)
    if role not in ("smm", "superadmin"):
        return await call.answer("Faqat SMM va SuperAdmin yubora oladi!", show_alert=True)

    await call.message.edit_text(
        "Reklama xabarini yuboring (foto, video, matn):",
        reply_markup=back_button()
    )
    await state.set_state(AdminStates.broadcast)


@router.message(AdminStates.broadcast)
async def broadcast_send(message: Message, state: FSMContext):
    async with async_session() as session:
        result = await session.execute(select(User.telegram_id))
        user_ids = [row[0] for row in result.all()]

    sent = 0
    blocked = 0
    for uid in user_ids:
        try:
            await message.copy_to(uid)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            blocked += 1

    await message.answer(f"Yuborildi: {sent} ta\nBloklagan: {blocked} ta")
    await state.clear()


# ====================== QR GENERATOR (faqat SuperAdmin) ======================
@router.callback_query(F.data == "admin_qr")
async def qr_start(call: CallbackQuery, state: FSMContext):
    if await get_role(call.from_user.id) != "superadmin":
        return await call.answer("Faqat SuperAdmin!", show_alert=True)
    

    async with async_session() as session:
        qr_codes = await session.execute(select(QRLog))
        qr_code = qr_codes.scalars().all()

    if qr_code:
        text = "<b>Mavjud QR kodlar:</b>\n\n";k=1
        for qr in qr_code:
            text += f"{k}. <b>{qr.source_key}</b>\n"
            k += 1
    else:
        text = "Hozircha QR kodlar mavjud emas."

    await call.message.edit_text(
        f"{text}\n\n"
        "QR kod uchun kalit yuboring (masalan: ice_city):",
        reply_markup=back_button()
    )
    
    await state.set_state(AdminStates.qr_key)


@router.message(AdminStates.qr_key)
async def qr_generate(message: Message, state: FSMContext):
    key = message.text.strip().lower()
    bot = await message.bot.get_me()
    link = f"https://t.me/{bot.username}?start={key}"
    file = generate_qr(link)

    await message.answer_photo(
        FSInputFile(file),
        caption=f"<b>{key.upper()}</b>\n\n{link}"
    )
    os.remove(file)

    async with async_session() as session:
        log = QRLog(
            admin_id=message.from_user.id,
            source_key=key
        )
        session.add(log)
        await session.commit()

    await state.clear()


# ====================== DAVOMAT (Cashier + Admin + SuperAdmin) ======================
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram import F
from sqlalchemy import select, or_, func
from datetime import date, datetime
from models import User, QRLog, AttendanceLog
from database import async_session  # o'z sessioning
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineQuery
# Admin kassir paneli
@router.callback_query(F.data == "admin_cashier")
async def cashier_start(call: CallbackQuery):
    role = await get_role(call.from_user.id)
    if role not in ("cashier", "admin", "superadmin"):
        return await call.answer("Faqat kassirlar ishlatadi!", show_alert=True)

    keyboards = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Qidirish", switch_inline_query_current_chat="")],
            [InlineKeyboardButton(text="Orqaga", callback_data="admin_main")]
        ]
    )
    await call.message.edit_text(
        "Foydalanuvchini qidiring:\n\n",
        parse_mode="HTML",
        reply_markup=keyboards
    )
    await call.answer("Inline qidiruv faollashtirildi!")


@router.inline_query(F.query.regexp(r"^\d{3,}|^@|^[a-zA-Z]"))
async def inline_search_users(inline_query: InlineQuery):
    query = inline_query.query.strip().lstrip("@")
    if len(query) < 2:
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(
                or_(
                    User.phone.ilike(f"%{query}%"),
                    User.username.ilike(f"%{query}%"),
                    User.first_name.ilike(f"%{query}%")
                )
            ).limit(20)
        )
        users = result.scalars().all()
        qr_result = await session.execute(select(QRLog))
        admin = await session.scalar(
            select(Admin).where(Admin.telegram_id == inline_query.from_user.id)
        )
        admin_role = admin.role if admin else "superadmin"

        if admin_role == "cashier":
            qr_places = [admin.place]
        else:
            qr_places = [row.source_key for row in qr_result.scalars().all()]

    results = []
    for user in users:
        text = f"<b>{user.first_name}</b>\nTelefon: {user.phone}\n"
        if user.username:
            text += f"Username: @{user.username}\n"

        buttons = [[
            InlineKeyboardButton(
                text=f"Kelgan — {place}",
                callback_data=f"mark_attend:{user.telegram_id}:{place}"
            )
        ] for place in qr_places]

        results.append(InlineQueryResultArticle(
            id=str(user.id),
            title=f"{user.first_name} | {user.phone}",
            description=f"@{user.username}" if user.username else "",
            input_message_content=InputTextMessageContent(
                message_text=f"{user.first_name} | {user.phone}\n@{user.username}" if user.username else f"{user.first_name} | {user.phone}"
            ),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="Ha ✔️",
                            callback_data=f"confirm_attend:{user.telegram_id}:{qr_places[0]}"),
                        InlineKeyboardButton(text="Yo‘q ❌",
                            callback_data="cancel_attend")
                    ]
                ]
            )
        ))



    await inline_query.answer(results, cache_time=1)

@router.callback_query(F.data.startswith("confirm_attend:"))
async def confirm_attend(call: CallbackQuery):
    _, user_tg_id, place = call.data.split(":")
    user_tg_id = int(user_tg_id)

    async with async_session() as session:

        result = await session.execute(select(User).where(User.telegram_id == user_tg_id))
        user = result.scalar_one_or_none()

        if not user:
            return await call.answer("Foydalanuvchi topilmadi", show_alert=True)

        log = AttendanceLog(
            user_id=user.telegram_id,
            place=place,
            marked_by=call.from_user.id
        )

        user.attended = True
        user.attended_date = datetime.utcnow()

        session.add(log)
        await session.commit()

    await call.answer("Belgilandi ✔️", show_alert=True)


@router.callback_query(F.data == "cancel_attend")
async def cancel_attend(call: CallbackQuery):
    await call.answer("Bekor qilindi ❌", show_alert=True)

# ====================== SUPERADMIN: ADMINLAR BOSHQARUVI ======================
@router.callback_query(F.data == "manage_admins")
async def manage_admins(call: CallbackQuery):
    if await get_role(call.from_user.id) != "superadmin":
        return await call.answer("Faqat SuperAdmin!", show_alert=True)

    async with async_session() as session:
        result = await session.execute(select(Admin))
        admins = result.scalars().all()

    if not admins:
        text = "Hozircha admin yo'q."
    else:
        text = "<b>Adminlar roʻyxati:</b>\n\n"
        for a in admins:
            text += f"• {a.telegram_id} — <b>{a.role.upper()}</b>\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi admin qo'shish", callback_data="add_admin")],
        [InlineKeyboardButton(text="➖ Admin o'chirish", callback_data="remove_admin")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_main")]
    ])

    await call.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "add_admin")
async def add_admin_start(call: CallbackQuery, state: FSMContext):
    if await get_role(call.from_user.id) != "superadmin":
        return
    await call.message.edit_text(
        "Yangi adminning <b>Telegram ID</b> raqamini yuboring:",
        reply_markup=back_button()
    )
    await state.set_state(SuperAdminStates.waiting_admin_id)


@router.message(SuperAdminStates.waiting_admin_id)
async def add_admin_role(message: Message, state: FSMContext):
    try:
        tg_id = int(message.text.strip())
        await state.update_data(tg_id=tg_id)
        await message.answer(
            "Endi rolni tanlang:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="SuperAdmin", callback_data="role_superadmin")],
                [InlineKeyboardButton(text="Analitik", callback_data="role_admin")],
                [InlineKeyboardButton(text="SMM", callback_data="role_smm")],
                [InlineKeyboardButton(text="Kassir", callback_data="role_cashier")],
                [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_main")]
            ])
        )
        await state.set_state(SuperAdminStates.waiting_admin_role)
    except:
        await message.answer("ID noto'g'ri! Faqat raqam yuboring.")


@router.callback_query(F.data.startswith("role_"), SuperAdminStates.waiting_admin_role)
async def add_admin_confirm(call: CallbackQuery, state: FSMContext):
    role_map = {
        "role_superadmin": "superadmin",
        "role_admin": "analyst",
        "role_smm": "smm",
        "role_cashier": "cashier"
    }
    role = role_map[call.data]

    data = await state.get_data()
    tg_id = data["tg_id"]

    async with async_session() as session:
        exists = await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        if exists:
            await call.message.edit_text(f"{tg_id} allaqachon admin!")
            await state.clear()
            return

        
        if role == "cashier":
            await state.update_data(role=role)
            await call.message.edit_text(
                "Kassir qaysi joyda ishlaydi?\nQR kodlar asosida joyni tanlang:",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    *[
                        [InlineKeyboardButton(text=qr.source_key, callback_data=f"cashier_place:{qr.source_key}")]
                        for qr in (await session.execute(select(QRLog))).scalars().all()
                    ],
                    [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_main")]
                ])
            )
            return
        new_admin = Admin(telegram_id=tg_id, role=role, added_by=call.from_user.id)
        session.add(new_admin)
        await session.commit()


    await call.message.edit_text(
        f"Yangi admin qo'shildi!\n\nID: <code>{tg_id}</code>\nRol: <b>{role.upper()}</b>",
        reply_markup=back_button()
    )
    await state.clear()

@router.callback_query(F.data.startswith("cashier_place:"))
async def set_cashier_place(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    tg_id = data["tg_id"]
    role = data["role"]
    place = call.data.split(":")[1]

    async with async_session() as session:
        new_admin = Admin(
            telegram_id=tg_id,
            role=role,
            place=place,
            added_by=call.from_user.id
        )
        session.add(new_admin)
        await session.commit()

    await call.message.edit_text(
        f"Kassir qo'shildi!\nID: {tg_id}\nJoy: <b>{place}</b>",
        reply_markup=back_button()
    )
    await state.clear()

# ====================== ADMIN O'CHIRISH ======================
@router.callback_query(F.data == "remove_admin")
async def remove_admin_start(call: CallbackQuery):
    if await get_role(call.from_user.id) != "superadmin":
        return

    async with async_session() as session:
        result = await session.execute(select(Admin))
        admins = result.scalars().all()

    if not admins:
        await call.message.edit_text("O'chirish uchun admin yo'q.", reply_markup=back_button())
        return

    kb = []
    for a in admins:
        if a.role != "superadmin":  # SuperAdminni o'chirmaslik
            kb.append([InlineKeyboardButton(
                text=f"{a.telegram_id} — {a.role.upper()}",
                callback_data=f"deladmin_{a.telegram_id}"
            )])

    # Faqat bir marta "Orqaga" tugmasi qo'shamiz
    kb.append([InlineKeyboardButton(text="Orqaga", callback_data="admin_main")])

    await call.message.edit_text(
        "<b>O'chirish uchun adminni tanlang:</b>",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
    )

@router.callback_query(F.data.startswith("deladmin_"))
async def remove_admin_confirm(call: CallbackQuery):
    tg_id = int(call.data.split("_")[1])

    async with async_session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == tg_id))
        if not admin:
            await call.answer("Topilmadi")
            return
        if admin.role == "superadmin":
            await call.answer("SuperAdmin o'chirib bo'lmaydi!", show_alert=True)
            return

        await session.delete(admin)
        await session.commit()

    await call.message.edit_text(f"{tg_id} adminlikdan olindi!", reply_markup=back_button())


# ====================== ORQAGA QAYTISH ======================
@router.callback_query(F.data == "admin_main")
async def back_to_main(call: CallbackQuery):
    role = await get_role(call.from_user.id)
    await call.message.edit_text(
        "Admin panel",
        reply_markup=admin_main_keyboard(role)
    )