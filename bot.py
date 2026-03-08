#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Support Helper Bot - Версия для Render.com
Работает через Flask + polling в отдельном потоке
"""

import asyncio
import logging
import json
import os
import random
import threading
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# ========== ТВОИ ДАННЫЕ ==========
BOT_TOKEN = "8678152372:AAHEqZ5Lxe6CsSZpX0loPyOioejOFYCTtoI"
OWNER_ID = 8402407852
CHANNEL_LINK = "https://t.me/+arKuZnc9R9hhNDIx"
# =================================

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== FLASK ДЛЯ RENDER ==========
app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "Bot is running!"})

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

def run_flask():
    """Запуск Flask в отдельном потоке"""
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
# ========================================

# Инициализация бота
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ========== КЛАССЫ СОСТОЯНИЙ ==========
class UserStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_admin_tag = State()
    in_dialog = State()
    waiting_for_complaint = State()

class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_tag = State()
    waiting_for_role = State()
    waiting_for_ban_reason = State()
    waiting_for_mute_time = State()
    waiting_for_unban_user = State()
    waiting_for_unmute_user = State()
    waiting_for_broadcast_text = State()
    waiting_for_broadcast_button = State()
    waiting_for_remove_admin_id = State()
    waiting_for_remove_admin_reason = State()

# ========== РАБОТА С ФАЙЛАМИ ==========
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

def load_data(filename: str) -> dict:
    try:
        with open(DATA_DIR / f"{filename}.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_data(filename: str, data: dict) -> None:
    with open(DATA_DIR / f"{filename}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ========== ДАННЫЕ ==========
users = load_data("users")
admins = load_data("admins")
dialogs = load_data("dialogs")
waiting_queue = load_data("queue")
pending_by_tag = load_data("pending_by_tag")
banlist = load_data("banlist")
mutelist = load_data("mutelist")
complaints = load_data("complaints")

def save_all():
    save_data("users", users)
    save_data("admins", admins)
    save_data("dialogs", dialogs)
    save_data("queue", waiting_queue)
    save_data("pending_by_tag", pending_by_tag)
    save_data("banlist", banlist)
    save_data("mutelist", mutelist)
    save_data("complaints", complaints)

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def is_admin(user_id: int) -> bool:
    return str(user_id) in admins

def is_senior_admin(user_id: int) -> bool:
    if str(user_id) not in admins:
        return False
    role = admins[str(user_id)]["role"]
    return role in ["ГЛ АДМИН", "СОВЛАДЕЛЕЦ", "ВЛАДЕЛЕЦ"]

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def is_banned(user_id: int) -> bool:
    return str(user_id) in banlist

def is_muted(user_id: int) -> bool:
    if str(user_id) not in mutelist:
        return False
    mute_until = datetime.fromisoformat(mutelist[str(user_id)]["until"])
    if datetime.now() > mute_until:
        del mutelist[str(user_id)]
        save_all()
        return False
    return True

def get_user_name(user_id: int) -> str:
    return users.get(str(user_id), {}).get("name", "Пользователь")

def get_admin_tag(user_id: int) -> str:
    return admins.get(str(user_id), {}).get("tag", "#unknown")

async def send_main_menu(user_id: int, text: str = "Главное меню"):
    if is_banned(user_id):
        await bot.send_message(
            user_id,
            f"❌ Вы забанены.\nПричина: {banlist[str(user_id)]['reason']}"
        )
        return
    
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("🎲 Позвать рандомно"))
    keyboard.add(KeyboardButton("🔍 Позвать админа (по тегу)"))
    
    await bot.send_message(user_id, text, reply_markup=keyboard)

async def send_admin_menu(user_id: int):
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("🎲 Подключиться рандомно"))
    keyboard.add(KeyboardButton("🔍 Подключиться по тегу"))
    
    if is_senior_admin(user_id) or is_owner(user_id):
        keyboard.add(KeyboardButton("👑 Админ-панель"))
    
    await bot.send_message(user_id, "Меню администратора:", reply_markup=keyboard)

# ========== ТАЙМЕР ДЛЯ ОЧЕРЕДИ ==========
async def queue_timeout(user_id: int):
    await asyncio.sleep(600)
    
    if str(user_id) in dialogs:
        return
    
    if user_id in waiting_queue:
        waiting_queue.remove(user_id)
        save_all()
        
        await bot.send_message(
            user_id,
            "⏰ Похоже, что все админы заняты.\n"
            "Попробуйте снова /start"
        )
        await send_main_menu(user_id)

# ========== СТАРТ ==========
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    if is_banned(user_id):
        await message.answer(
            f"❌ Вы забанены.\nПричина: {banlist[str(user_id)]['reason']}"
        )
        return
    
    if str(user_id) in users:
        if str(user_id) in dialogs:
            admin_id = dialogs[str(user_id)]
            admin_tag = get_admin_tag(int(admin_id))
            await UserStates.in_dialog.set()
            await message.answer(
                f"🔔 К вам подключился Админ {admin_tag}. Приятного общения!"
            )
            return
        
        await send_main_menu(user_id)
        return
    
    await UserStates.waiting_for_name.set()
    
    await message.answer(
        "👋 Здравствуй, тебе нужна поддержка? Тебе грустно? ЗАБУДЬ ДРУГИХ БОТОВ!\n\n"
        "Наш совершенно другой, с отличным функционалом и без ответа ты точно не останешься! Мы ценим каждого пользователя!\n\n"
        "Извини что отвлекаю, можешь подписаться на наш канал, это необязательно, но мы будем рады)"
    )
    
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔔 Подписаться", url=CHANNEL_LINK))
    await message.answer("Подписка:", reply_markup=keyboard)
    
    await message.answer("📝 Как вас зовут?")

@dp.message_handler(state=UserStates.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    name = message.text.strip()
    
    users[str(user_id)] = {
        "name": name,
        "username": message.from_user.username,
        "registered": datetime.now().isoformat()
    }
    save_all()
    
    await message.answer(f"✅ Приятно познакомиться, {name}!")
    await send_main_menu(user_id)
    await state.finish()

# ========== КОМАНДА /END ==========
@dp.message_handler(commands=['end'])
async def cmd_end(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    if str(user_id) in dialogs:
        admin_id = dialogs[str(user_id)]
        del dialogs[str(user_id)]
        save_all()
        
        await bot.send_message(
            int(admin_id),
            "🔚 Пользователь завершил диалог."
        )
        
        await message.answer("✅ Диалог завершён.")
        await send_main_menu(user_id)
        await state.finish()
    
    elif str(user_id) in [v for v in dialogs.values()]:
        user_id_str = None
        for uid, aid in dialogs.items():
            if aid == str(user_id):
                user_id_str = uid
                break
        
        if user_id_str:
            del dialogs[user_id_str]
            save_all()
            
            await bot.send_message(
                int(user_id_str),
                "🔚 Администратор завершил диалог.\n\n"
                "Если админ был к вам невежлив, груб и т.д., нажмите «Позвать админа» и введите тег: #крип, чтобы объяснить ситуацию."
            )
            await send_main_menu(int(user_id_str))
            
            await message.answer("✅ Диалог завершён.")
            await send_admin_menu(user_id)
            await state.finish()
    
    else:
        await message.answer("❌ У вас нет активного диалога.")

# ========== ОБРАБОТКА КНОПОК ПОЛЬЗОВАТЕЛЯ ==========
@dp.message_handler(lambda message: message.text == "🎲 Позвать рандомно")
async def user_call_random(message: types.Message):
    user_id = message.from_user.id
    
    if is_banned(user_id):
        await message.answer(f"❌ Вы забанены.\nПричина: {banlist[str(user_id)]['reason']}")
        return
    
    if is_muted(user_id):
        await message.answer(f"❌ Вы в муте.")
        return
    
    if str(user_id) in dialogs:
        await message.answer("❌ У вас уже есть активный диалог.")
        return
    
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("✅ Продолжить"))
    keyboard.add(KeyboardButton("❌ Отмена"))
    
    await message.answer(
        "❓ Вы уверены что хотите позвать рандомного Админа?",
        reply_markup=keyboard
    )

@dp.message_handler(lambda message: message.text == "✅ Продолжить")
async def user_confirm_random(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in waiting_queue:
        waiting_queue.append(user_id)
        save_all()
    
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("❌ Отмена"))
    
    await message.answer(
        "⏳ Вы в очереди.",
        reply_markup=keyboard
    )
    
    asyncio.create_task(queue_timeout(user_id))
    
    for admin_id in admins.keys():
        if not is_banned(int(admin_id)):
            await bot.send_message(
                int(admin_id),
                f"👤 Пользователь {get_user_name(user_id)} ищет админа."
            )

@dp.message_handler(lambda message: message.text == "❌ Отмена")
async def user_cancel(message: types.Message):
    user_id = message.from_user.id
    
    if user_id in waiting_queue:
        waiting_queue.remove(user_id)
        save_all()
    
    await send_main_menu(user_id)

@dp.message_handler(lambda message: message.text == "🔍 Позвать админа (по тегу)")
async def user_call_by_tag(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    
    if is_banned(user_id):
        await message.answer(f"❌ Вы забанены.\nПричина: {banlist[str(user_id)]['reason']}")
        return
    
    if is_muted(user_id):
        await message.answer(f"❌ Вы в муте.")
        return
    
    if str(user_id) in dialogs:
        await message.answer("❌ У вас уже есть активный диалог.")
        return
    
    await UserStates.waiting_for_admin_tag.set()
    
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("❌ Отмена"))
    
    await message.answer(
        "🔍 Введите тег админа. Пример: #Дил",
        reply_markup=keyboard
    )

@dp.message_handler(state=UserStates.waiting_for_admin_tag)
async def process_admin_tag(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    tag = message.text.strip()
    
    if tag == "❌ Отмена":
        await send_main_menu(user_id)
        await state.finish()
        return
    
    admin_id = None
    for aid, data in admins.items():
        if data["tag"] == tag:
            admin_id = int(aid)
            break
    
    if not admin_id:
        await message.answer("❌ Админ с таким тегом не найден.")
        await state.finish()
        return
    
    if str(admin_id) in dialogs.values():
        await message.answer("❌ Этот админ сейчас занят.")
        await state.finish()
        return
    
    if str(admin_id) not in pending_by_tag:
        pending_by_tag[str(admin_id)] = []
    
    if user_id not in pending_by_tag[str(admin_id)]:
        pending_by_tag[str(admin_id)].append(user_id)
        save_all()
    
    await message.answer(f"✅ Запрос отправлен админу {tag}.")
    
    await bot.send_message(
        admin_id,
        f"👤 Пользователь {get_user_name(user_id)} зовёт вас в диалог (тег {tag})."
    )
    
    await state.finish()

# ========== ОБРАБОТКА КНОПОК АДМИНА ==========
@dp.message_handler(lambda message: message.text == "🎲 Подключиться рандомно")
async def admin_connect_random(message: types.Message):
    admin_id = message.from_user.id
    
    if not is_admin(admin_id):
        return
    
    if not waiting_queue:
        await message.answer("📭 Нет пользователей в очереди.")
        return
    
    text = "📋 Ожидающие пользователи:\n\n"
    for i, uid in enumerate(waiting_queue, 1):
        text += f"{i}. {get_user_name(uid)} (ID: {uid})\n"
    
    text += "\nВведите номер пользователя:"
    
    await AdminStates.waiting_for_user_id.set()
    await message.answer(text)

@dp.message_handler(state=AdminStates.waiting_for_user_id)
async def process_user_id_selection(message: types.Message, state: FSMContext):
    admin_id = message.from_user.id
    
    try:
        index = int(message.text.strip()) - 1
        user_id = waiting_queue[index]
    except:
        await message.answer("❌ Неверный номер.")
        await state.finish()
        return
    
    waiting_queue.remove(user_id)
    dialogs[str(user_id)] = str(admin_id)
    save_all()
    
    admin_tag = get_admin_tag(admin_id)
    
    await bot.send_message(
        user_id,
        f"🔔 К вам подключился Админ {admin_tag}. Приятного общения!"
    )
    
    await message.answer(f"✅ Вы подключились к пользователю {get_user_name(user_id)}.")
    await send_admin_menu(admin_id)
    await state.finish()

@dp.message_handler(lambda message: message.text == "🔍 Подключиться по тегу")
async def admin_connect_by_tag(message: types.Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_admin(admin_id):
        return
    
    if str(admin_id) not in pending_by_tag or not pending_by_tag[str(admin_id)]:
        await message.answer("📭 Нет пользователей, которые позвали вас.")
        return
    
    text = "📋 Пользователи, ожидающие вас:\n\n"
    for i, uid in enumerate(pending_by_tag[str(admin_id)], 1):
        text += f"{i}. {get_user_name(uid)} (ID: {uid})\n"
    
    text += "\nВведите номер пользователя:"
    
    await AdminStates.waiting_for_user_id.set()
    await message.answer(text)

# ========== АДМИН-ПАНЕЛЬ (сокращенно для примера, можно добавить все функции) ==========
@dp.message_handler(lambda message: message.text == "👑 Админ-панель")
async def admin_panel(message: types.Message):
    admin_id = message.from_user.id
    
    if not is_senior_admin(admin_id) and not is_owner(admin_id):
        return
    
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("📋 Список пользователей"))
    keyboard.add(KeyboardButton("📋 Список админов"))
    keyboard.add(KeyboardButton("➕ Выдать админку"))
    keyboard.add(KeyboardButton("➖ Удалить админа"))
    keyboard.add(KeyboardButton("◀️ Назад"))
    
    await message.answer("👑 Админ-панель", reply_markup=keyboard)

@dp.message_handler(lambda message: message.text == "📋 Список пользователей")
async def list_users(message: types.Message):
    admin_id = message.from_user.id
    
    if not is_senior_admin(admin_id) and not is_owner(admin_id):
        return
    
    if not users:
        await message.answer("📭 Нет пользователей.")
        return
    
    text = "📋 **Все пользователи:**\n\n"
    for uid, data in list(users.items())[:50]:
        username = data.get("username", "")
        name = data.get("name", "Unknown")
        username_str = f"@{username}" if username else "—"
        text += f"👤 {name} | {username_str} | ID: {uid}\n"
    
    await message.answer(text)

@dp.message_handler(lambda message: message.text == "📋 Список админов")
async def list_admins(message: types.Message):
    admin_id = message.from_user.id
    
    if not is_senior_admin(admin_id) and not is_owner(admin_id):
        return
    
    if not admins:
        await message.answer("📭 Нет админов.")
        return
    
    text = "👑 **Все администраторы:**\n\n"
    for uid, data in admins.items():
        user_data = users.get(uid, {})
        username = user_data.get("username", "")
        name = user_data.get("name", "Unknown")
        username_str = f"@{username}" if username else "—"
        text += f"👑 {data['tag']} | {name} | {username_str} | ID: {uid} | Роль: {data['role']}\n"
    
    await message.answer(text)

@dp.message_handler(lambda message: message.text == "➕ Выдать админку")
async def give_admin(message: types.Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_senior_admin(admin_id) and not is_owner(admin_id):
        return
    
    await AdminStates.waiting_for_user_id.set()
    
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("❌ Отмена"))
    
    await message.answer(
        "👤 Введите ID пользователя, которому хотите выдать админку:",
        reply_markup=keyboard
    )

@dp.message_handler(state=AdminStates.waiting_for_user_id)
async def process_give_admin_user(message: types.Message, state: FSMContext):
    target_id = message.text.strip()
    
    if target_id == "❌ Отмена":
        await admin_panel(message)
        await state.finish()
        return
    
    if target_id not in users:
        await message.answer("❌ Пользователь с таким ID не найден.")
        await state.finish()
        return
    
    await state.update_data(target_admin_id=target_id)
    await AdminStates.waiting_for_tag.set()
    
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("❌ Отмена"))
    
    await message.answer(
        "🏷 Введите тег для админа (с #, например #Дил):",
        reply_markup=keyboard
    )

@dp.message_handler(state=AdminStates.waiting_for_tag)
async def process_give_admin_tag(message: types.Message, state: FSMContext):
    tag = message.text.strip()
    
    if tag == "❌ Отмена":
        await admin_panel(message)
        await state.finish()
        return
    
    if not tag.startswith("#"):
        await message.answer("❌ Тег должен начинаться с #")
        return
    
    for data in admins.values():
        if data["tag"] == tag:
            await message.answer("❌ Такой тег уже существует.")
            return
    
    await state.update_data(admin_tag=tag)
    await AdminStates.waiting_for_role.set()
    
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("АДМИН"))
    keyboard.add(KeyboardButton("ГЛ АДМИН"))
    keyboard.add(KeyboardButton("СОВЛАДЕЛЕЦ"))
    keyboard.add(KeyboardButton("ВЛАДЕЛЕЦ"))
    keyboard.add(KeyboardButton("❌ Отмена"))
    
    await message.answer("👑 Выберите роль:", reply_markup=keyboard)

@dp.message_handler(state=AdminStates.waiting_for_role)
async def process_give_admin_role(message: types.Message, state: FSMContext):
    role = message.text.strip()
    valid_roles = ["АДМИН", "ГЛ АДМИН", "СОВЛАДЕЛЕЦ", "ВЛАДЕЛЕЦ"]
    
    if role == "❌ Отмена":
        await admin_panel(message)
        await state.finish()
        return
    
    if role not in valid_roles:
        await message.answer("❌ Выберите роль из списка.")
        return
    
    data = await state.get_data()
    target_id = data.get("target_admin_id")
    tag = data.get("admin_tag")
    
    admins[target_id] = {
        "tag": tag,
        "role": role,
        "issued_by": message.from_user.id,
        "date": datetime.now().isoformat()
    }
    save_all()
    
    await message.answer(f"✅ Админка выдана! ID: {target_id}, Тег: {tag}, Роль: {role}")
    
    await bot.send_message(
        int(target_id),
        f"👑 Вам выданы права администратора!\nТег: {tag}\nРоль: {role}"
    )
    
    await admin_panel(message)
    await state.finish()

@dp.message_handler(lambda message: message.text == "➖ Удалить админа")
async def remove_admin(message: types.Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_senior_admin(admin_id) and not is_owner(admin_id):
        return
    
    await AdminStates.waiting_for_remove_admin_id.set()
    
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("❌ Отмена"))
    
    await message.answer(
        "👤 Введите ID админа, которого хотите удалить:",
        reply_markup=keyboard
    )

@dp.message_handler(state=AdminStates.waiting_for_remove_admin_id)
async def process_remove_admin_id(message: types.Message, state: FSMContext):
    target_id = message.text.strip()
    
    if target_id == "❌ Отмена":
        await admin_panel(message)
        await state.finish()
        return
    
    if target_id not in admins:
        await message.answer("❌ Админ с таким ID не найден.")
        await state.finish()
        return
    
    if int(target_id) == OWNER_ID:
        await message.answer("❌ Нельзя удалить владельца.")
        await state.finish()
        return
    
    await state.update_data(remove_admin_id=target_id)
    await AdminStates.waiting_for_remove_admin_reason.set()
    
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton("❌ Отмена"))
    
    await message.answer(
        "📝 Введите причину удаления:",
        reply_markup=keyboard
    )

@dp.message_handler(state=AdminStates.waiting_for_remove_admin_reason)
async def process_remove_admin_reason(message: types.Message, state: FSMContext):
    reason = message.text.strip()
    
    if reason == "❌ Отмена":
        await admin_panel(message)
        await state.finish()
        return
    
    data = await state.get_data()
    target_id = data.get("remove_admin_id")
    admin_tag = admins[target_id]["tag"]
    
    del admins[target_id]
    save_all()
    
    await message.answer(f"✅ Админ {target_id} ({admin_tag}) удалён.")
    
    await bot.send_message(
        int(target_id),
        f"❌ Вы лишены прав администратора.\nПричина: {reason}"
    )
    
    await admin_panel(message)
    await state.finish()

@dp.message_handler(lambda message: message.text == "◀️ Назад")
async def back_to_admin_menu(message: types.Message):
    admin_id = message.from_user.id
    
    if is_senior_admin(admin_id) or is_owner(admin_id):
        await admin_panel(message)
    else:
        await send_admin_menu(admin_id)

# ========== ЗАПУСК БОТА ==========
def run_bot():
    """Запуск бота в отдельном потоке"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True, loop=loop)

# ========== ГЛАВНЫЙ ЗАПУСК ==========
if __name__ == "__main__":
    logger.info("Запуск Flask для Render...")
    
    # Запускаем Flask в отдельном потоке
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    logger.info("Запуск бота...")
    # Запускаем бота в главном потоке
    run_bot()
