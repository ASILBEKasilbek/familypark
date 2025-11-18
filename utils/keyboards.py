# user/keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import os

def subscription_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Obuna bo‘lish", url=f"https://t.me/{os.getenv('CHANNEL_USERNAME')}")],
        [InlineKeyboardButton(text="Obuna bo‘ldim", callback_data="check_subscription")]
    ])

def phone_keyboard():
    btn = KeyboardButton(text="Raqam yuborish", request_contact=True)
    return ReplyKeyboardMarkup([[btn]], resize_keyboard=True, one_time_keyboard=True)