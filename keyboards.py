from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from config import OWNER_ID
from database import is_senior_admin, is_owner

def main_menu(user_id: int) -> ReplyKeyboardMarkup:
    """Главное меню пользователя"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🎲 Позвать рандомно"))
    builder.add(KeyboardButton(text="🔍 Позвать админа (по тегу)"))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def admin_menu(user_id: int) -> ReplyKeyboardMarkup:
    """Меню администратора"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="🎲 Подключиться рандомно"))
    builder.add(KeyboardButton(text="🔍 Подключиться по тегу"))
    
    if is_senior_admin(user_id) or is_owner(user_id):
        builder.add(KeyboardButton(text="👑 Админ-панель"))
    
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def admin_panel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура админ-панели"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="📋 Список пользователей"))
    builder.add(KeyboardButton(text="📋 Список админов"))
    builder.add(KeyboardButton(text="➕ Выдать админку"))
    builder.add(KeyboardButton(text="➖ Удалить админа"))
    builder.add(KeyboardButton(text="🚫 Бан пользователя"))
    builder.add(KeyboardButton(text="✅ Разбан"))
    builder.add(KeyboardButton(text="🔇 Мут"))
    builder.add(KeyboardButton(text="🔊 Размут"))
    builder.add(KeyboardButton(text="📢 Рассылка"))
    builder.add(KeyboardButton(text="⚠️ Жалобы (#крип)"))
    builder.add(KeyboardButton(text="◀️ Назад"))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def cancel_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура с кнопкой отмены"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)

def confirm_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура подтверждения"""
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="✅ Продолжить"))
    builder.add(KeyboardButton(text="❌ Отмена"))
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)

def channel_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с ссылкой на канал"""
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="🔔 Подписаться", url=CHANNEL_LINK))
    return builder.as_markup()
