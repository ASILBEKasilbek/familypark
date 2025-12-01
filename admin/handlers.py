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
from sqlalchemy import select, func, delete, cast, String, or_
from datetime import datetime, date, timedelta
import os
import asyncio
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.types import InlineQuery



router = Router()

# States
class AdminStates(StatesGroup):
    broadcast = State()
    broadcast_message = State()
    qr_key = State()
    cashier_search = State()

class SuperAdminStates(StatesGroup):
    waiting_admin_id = State()
    waiting_admin_role = State()
    waiting_remove_admin = State()


def _personalized_block(first_name, base_text: str) -> str:
    name = first_name or "do'stimiz"
    greeting = f"👋 Salom, {name}!"
    return f"{greeting}\n\n{base_text}" if base_text else greeting


async def _resolve_accessible_places(session, admin_record):
    if admin_record and admin_record.role == "cashier" and admin_record.place:
        return [admin_record.place]
    result = await session.execute(select(QRLog.source_key))
    return [row[0] for row in result.all()]


async def _mark_attendance(session, user, place: str, marker_id: int) -> datetime:
    now = datetime.utcnow()
    log = AttendanceLog(
        user_id=user.telegram_id,
        place=place,
        marked_by=marker_id
    )
    user.attended = True
    user.attended_date = now
    session.add(log)
    await session.commit()
    return now


async def _notify_attendance(bot, user, place: str, marked_at: datetime):
    formatted_time = marked_at.strftime("%Y-%m-%d %H:%M:%S")
    await bot.send_message(
        chat_id=user.telegram_id,
        text=(
            f"👋 Salom, {user.first_name}!\n\n"
            f"✅ Siz muvaffaqiyatli ravishda quyidagi joyga keldingiz:\n"
            f"🏢 Joy: <b>{place}</b>\n"
            f"🕒 Vaqt: <b>{formatted_time}</b>\n\n"
            f"Rahmat!"
        ),
        parse_mode="HTML"
    )


def _broadcast_target_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Hamma", callback_data="broadcast_target:all")],
            [InlineKeyboardButton(text="Faqat erkaklar", callback_data="broadcast_target:male")],
            [InlineKeyboardButton(text="Faqat ayollar", callback_data="broadcast_target:female")],
            [InlineKeyboardButton(text="Orqaga", callback_data="admin_main")]
        ]
    )


async def _find_user_by_identifier(session, identifier: str):
    value = identifier.strip()
    user = None

    if value.startswith("@"):
        username = value[1:]
        if username:
            user = await session.scalar(
                select(User).where(func.lower(User.username) == username.lower())
            )

    if user is None and value.isdigit():
        numeric_value = int(value)
        user = await session.scalar(select(User).where(User.telegram_id == numeric_value))
        if user is None:
            user = await session.scalar(select(User).where(User.id == numeric_value))

    if user is None:
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits:
            user = await session.scalar(select(User).where(User.phone == digits))

    return user


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


@router.callback_query(F.data == "cashier_report")
async def cashier_report(call: CallbackQuery):
    role = await get_role(call.from_user.id)
    if role not in ("admin", "superadmin", "analyst"):
        return await call.answer("Sizda ruxsat yo'q!", show_alert=True)

    today = datetime.utcnow().date()
    period_start = today.replace(day=1)
    next_month = (period_start + timedelta(days=32)).replace(day=1)
    start_dt = datetime.combine(period_start, datetime.min.time())
    end_dt = datetime.combine(next_month, datetime.min.time())

    async with async_session() as session:
        result = await session.execute(
            select(
                AttendanceLog.marked_by,
                func.count(AttendanceLog.id).label("total"),
                Admin.full_name,
                Admin.place
            )
            .join(Admin, Admin.telegram_id == AttendanceLog.marked_by, isouter=True)
            .where(AttendanceLog.marked_at >= start_dt, AttendanceLog.marked_at < end_dt)
            .group_by(AttendanceLog.marked_by, Admin.full_name, Admin.place)
            .order_by(func.count(AttendanceLog.id).desc())
        )
        rows = result.all()

    if not rows:
        return await call.answer("Bu oyda hali ma'lumot yo'q.", show_alert=True)

    month_label = period_start.strftime("%B %Y")
    text = [f"<b>{month_label}</b> bo'yicha kassirlar hisobot:"]
    for idx, row in enumerate(rows, 1):
        marked_by, total, full_name, place = row
        name = full_name or "Ism kiritilmagan"
        place_part = f" | Joy: {place}" if place else ""
        text.append(f"{idx}. {name} ({marked_by}) — {total} ta{place_part}")

    text.append("\nHisobot hozirgi oyni qamrab oladi.")
    await call.message.edit_text("\n".join(text), reply_markup=back_button())


# ====================== BROADCAST (SMM + SuperAdmin) ======================
@router.callback_query(F.data == "admin_broadcast")
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    role = await get_role(call.from_user.id)
    if role not in ("smm", "superadmin"):
        return await call.answer("Faqat SMM va SuperAdmin yubora oladi!", show_alert=True)

    await call.message.edit_text(
        "Xabar kimlarga yuboriladi?",
        reply_markup=_broadcast_target_keyboard()
    )
    await state.set_state(AdminStates.broadcast)


@router.callback_query(AdminStates.broadcast, F.data.startswith("broadcast_target:"))
async def broadcast_target_selected(call: CallbackQuery, state: FSMContext):
    target = call.data.split(":")[1]
    await state.update_data(broadcast_target=target)
    await call.message.edit_text(
        "Reklama xabarini yuboring (foto, video, matn):",
        reply_markup=back_button()
    )
    await state.set_state(AdminStates.broadcast_message)


@router.message(AdminStates.broadcast_message)
async def broadcast_send(message: Message, state: FSMContext):
    data = await state.get_data()
    target = data.get("broadcast_target", "all")

    async with async_session() as session:
        stmt = select(User.telegram_id, User.first_name)
        if target in ("male", "female"):
            stmt = stmt.where(User.gender == target)
        result = await session.execute(stmt)
        receivers = result.all()

    if not receivers:
        await message.answer("Tanlangan toifadagi foydalanuvchilar topilmadi.")
        await state.clear()
        return

    sent = 0
    blocked = 0
    for uid, first_name in receivers:
        try:
            if message.content_type == "text":
                base_text = message.html_text or message.text or ""
                text = _personalized_block(first_name, base_text)
                await message.bot.send_message(uid, text, parse_mode="HTML")
            else:
                base_caption = message.html_caption or message.caption or ""
                caption = _personalized_block(first_name, base_caption)
                await message.copy_to(uid, caption=caption, parse_mode="HTML")
            sent += 1
        except Exception:
            blocked += 1
        await asyncio.sleep(0.05)

    target_label = {
        "all": "Hamma",
        "male": "Erkaklar",
        "female": "Ayollar"
    }.get(target, target)

    await message.answer(f"Yuborildi: {sent} ta\nBloklagan: {blocked} ta\nSegment: {target_label}")
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

# Admin kassir paneli
@router.callback_query(F.data == "admin_cashier")
async def cashier_start(call: CallbackQuery, state: FSMContext):
    await state.clear()
    role = await get_role(call.from_user.id)
    if role not in ("cashier", "admin", "superadmin"):
        return await call.answer("Faqat kassirlar ishlatadi!", show_alert=True)

    keyboards = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Qidirish", switch_inline_query_current_chat="")],
            [InlineKeyboardButton(text="ID orqali belgilash", callback_data="admin_attend_id")],
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
    if not await is_admin(inline_query.from_user.id):
        return await inline_query.answer(
            results=[],
            switch_pm_text="HA ha qiziqishga yozib kurdizmi admin emaskusiz!",
            switch_pm_parameter="no_access",  
            cache_time=1
        )

    query = inline_query.query.strip().lstrip("@")
    if len(query) < 2:
        return

    async with async_session() as session:
        result = await session.execute(
            select(User).where(
                or_(
                    cast(User.phone, String).ilike(f"%{query}%"),
                    cast(User.telegram_id, String).ilike(f"%{query}%"),
                    User.first_name.ilike(f"%{query}%")
                )
            ).limit(20)
        )
        users = result.scalars().all()
        admin = await session.scalar(
            select(Admin).where(Admin.telegram_id == inline_query.from_user.id)
        )
        qr_places = await _resolve_accessible_places(session, admin)
        if not qr_places:
            qr_places = ["main"]

    results = []
    for user in users:
        text = f"<b>{user.first_name}</b>\nTelefon: {user.phone}\n"
        if user.username:
            text += f"Username: @{user.username}\n"

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


@router.callback_query(F.data == "admin_attend_id")
async def attend_by_id_start(call: CallbackQuery, state: FSMContext):
    if not await is_admin(call.from_user.id):
        return await call.answer("Ruxsat yo'q!", show_alert=True)

    async with async_session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == call.from_user.id))
        places = await _resolve_accessible_places(session, admin)

    if not places:
        return await call.answer("Avval QR joylarini yarating!", show_alert=True)

    await state.update_data(attend_places=places)
    await call.message.edit_text(
        "Foydalanuvchining Telegram ID, telefon raqami yoki username ni yuboring:",
        reply_markup=back_button("admin_cashier")
    )
    await state.set_state(AdminStates.cashier_search)


@router.message(AdminStates.cashier_search)
async def attend_by_id_lookup(message: Message, state: FSMContext):
    identifier = message.text.strip()
    marked_at = None
    place_used = None

    async with async_session() as session:
        user = await _find_user_by_identifier(session, identifier)
        if not user:
            await message.answer("Foydalanuvchi topilmadi. Qaytadan urinib ko'ring.")
            return

        data = await state.get_data()
        places = data.get("attend_places") or []
        if not places:
            admin = await session.scalar(select(Admin).where(Admin.telegram_id == message.from_user.id))
            places = await _resolve_accessible_places(session, admin)
            await state.update_data(attend_places=places)

        if not places:
            await message.answer("Sizga joy biriktirilmagan. SuperAdmin bilan bog'laning.")
            return

        if len(places) == 1:
            place_used = places[0]
            marked_at = await _mark_attendance(session, user, place_used, message.from_user.id)
            await message.answer(f"{user.first_name} uchun {place_used} joyi belgilandi.")
        else:
            buttons = [
                [InlineKeyboardButton(text=place, callback_data=f"attend_place:{user.telegram_id}:{place}")]
                for place in places
            ]
            await message.answer(
                "Qaysi joyda belgilaymiz?",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
            )
            return

    if marked_at and place_used:
        await _notify_attendance(message.bot, user, place_used, marked_at)


@router.callback_query(F.data.startswith("attend_place:"))
async def attend_place_callback(call: CallbackQuery):
    _, user_tg_id, place = call.data.split(":", 2)
    user_tg_id = int(user_tg_id)

    async with async_session() as session:
        admin = await session.scalar(select(Admin).where(Admin.telegram_id == call.from_user.id))
        places = await _resolve_accessible_places(session, admin)
        if place not in places:
            return await call.answer("Bu joy sizga biriktirilmagan!", show_alert=True)

        result = await session.execute(select(User).where(User.telegram_id == user_tg_id))
        user = result.scalar_one_or_none()
        if not user:
            return await call.answer("Foydalanuvchi topilmadi", show_alert=True)

        marked_at = await _mark_attendance(session, user, place, call.from_user.id)

    await call.answer("Belgilandi ✔️", show_alert=True)
    await _notify_attendance(call.bot, user, place, marked_at)


@router.callback_query(F.data.startswith("confirm_attend:"))
async def confirm_attend(call: CallbackQuery):
    _, user_tg_id, place = call.data.split(":")
    user_tg_id = int(user_tg_id)

    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == user_tg_id))
        user = result.scalar_one_or_none()

        if not user:
            return await call.answer("Foydalanuvchi topilmadi", show_alert=True)
        marked_at = await _mark_attendance(session, user, place, call.from_user.id)
    
    await call.answer("Belgilandi ✔️", show_alert=True)
    await _notify_attendance(call.bot, user, place, marked_at)


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