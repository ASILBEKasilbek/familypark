# user/keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv
import os

load_dotenv()

def subscription_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Obuna bo‘lish", url=f"https://t.me/{os.getenv('CHANNEL_USERNAME')}")],
        [InlineKeyboardButton(text="Obuna bo‘ldim", callback_data="check_sub")]
    ])


def phone_keyboard():
    btn = KeyboardButton(text="Raqam yuborish", request_contact=True)
    return ReplyKeyboardMarkup(
        keyboard=[[btn]],
        resize_keyboard=True,
        one_time_keyboard=True
    )


def gender_keyboard():
    male = KeyboardButton(text="Erkak")
    female = KeyboardButton(text="Ayol")
    return ReplyKeyboardMarkup(
        keyboard=[[male, female]],
        resize_keyboard=True,
        one_time_keyboard=True
    )