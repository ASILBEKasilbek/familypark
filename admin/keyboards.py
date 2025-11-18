# admin/keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_main_keyboard(role: str) -> InlineKeyboardMarkup:
    kb = []

    # Har bir rol uchun ko'rinadigan tugmalar
    if role in ("analyst", "admin", "superadmin"):
        kb.append([InlineKeyboardButton(text="Statistika", callback_data="admin_stats")])

    if role in ("admin", "superadmin","analyst"):
        kb.append([InlineKeyboardButton(text="Excel eksport", callback_data="admin_export")])

    if role in ("smm", "superadmin"):
        kb.append([InlineKeyboardButton(text="Broadcast", callback_data="admin_broadcast")])

    if role == "superadmin":
        kb.append([InlineKeyboardButton(text="QR generatsiya", callback_data="admin_qr")])

    if role in ("cashier", "admin", "superadmin"):
        kb.append([InlineKeyboardButton(text="Kelganlarni belgilash", callback_data="admin_cashier")])

    if role == "superadmin":
        kb.append([InlineKeyboardButton(text="Adminlar boshqaruvi", callback_data="manage_admins")])

    # kb.append([InlineKeyboardButton(text="Yangilash", callback_data="admin_main")])

    return InlineKeyboardMarkup(inline_keyboard=kb)


def back_button(to: str = "admin_main"):
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Orqaga", callback_data=to)]]
    )

def admin_list_keyboard(admins: list) -> InlineKeyboardMarkup:
    kb = []
    for admin in admins:
        button_text = f"{admin.telegram_id} - {admin.role}"
        kb.append([InlineKeyboardButton(text=button_text, callback_data=f"admin_detail:{admin.telegram_id}")])
    kb.append([InlineKeyboardButton(text="Orqaga", callback_data="manage_admins")])
    return InlineKeyboardMarkup(inline_keyboard=kb)