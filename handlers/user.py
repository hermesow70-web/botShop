
import asyncio
import re
import random
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from config import OWNER_ID, CHANNEL_LINK
from database import (
    users, admins, dialogs, waiting_queue, pending_by_tag,
    complaints, banlist, mutelist, save_all,
    is_banned, is_muted, is_admin, is_senior_admin, is_owner,
    get_user_name, get_admin_tag
)
from states import UserStates, AdminStates
from keyboards import (
    main_menu, admin_menu, cancel_keyboard,
    confirm_keyboard, channel_keyboard
)

user_router = Router()

# Таймер для очереди
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
@user_router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Очищаем состояние
    await state.clear()
    
    # Проверка на бан
    if is_banned(user_id):
        await message.answer(
            f"❌ Вы забанены.\nПричина: {banlist[str(user_id)]['reason']}"
        )
        return
    
    # Если пользователь уже есть в базе
    if str(user_id) in users:
        # Проверка на активный диалог
        if str(user_id) in dialogs:
            admin_id = dialogs[str(user_id)]
            admin_tag = get_admin_tag(int(admin_id))
            await state.set_state(UserStates.in_dialog)
            await message.answer(
                f"🔔 К вам подключился Админ {admin_tag}. Приятного общения!"
            )
            return
        
        # Отправляем главное меню
        await message.answer(
            "Главное меню:",
            reply_markup=main_menu(user_id)
        )
        return
    
    # Новый пользователь - запрашиваем имя
    await state.set_state(UserStates.waiting_for_name)
    
    await message.answer(
        "👋 Здравствуй, тебе нужна поддержка? Тебе грустно? ЗАБУДЬ ДРУГИХ БОТОВ!\n\n"
        "Наш совершенно другой, с отличным функционалом и без ответа ты точно не останешься! Мы ценим каждого пользователя!\n\n"
        "Извини что отвлекаю, можешь подписаться на наш канал, это необязательно, но мы будем рады)"
    )
    
    await message.answer(
        "Подписка:",
        reply_markup=channel_keyboard()
    )
    
    await message.answer("📝 Как вас зовут?")

@user_router.message(UserStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    user_id = message.from_user.id
    name = message.text.strip()
    
    # Сохраняем пользователя
    users[str(user_id)] = {
        "name": name,
        "username": message.from_user.username,
        "registered": datetime.now().isoformat()
    }
    save_all()
    
    await message.answer(f"✅ Приятно познакомиться, {name}!")
    await message.answer(
        "Главное меню:",
        reply_markup=main_menu(user_id)
    )
    await state.clear()

# ========== КОМАНДА /END ==========
@user_router.message(Command("end"))
async def cmd_end(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Если пользователь в диалоге
    if str(user_id) in dialogs:
        admin_id = dialogs[str(user_id)]
        del dialogs[str(user_id)]
        save_all()
        
        # Уведомляем админа
        await bot.send_message(
            int(admin_id),
            "🔚 Пользователь завершил диалог.",
            reply_markup=admin_menu(int(admin_id))
        )
        
        await message.answer("✅ Диалог завершён.")
        await message.answer(
            "Главное меню:",
            reply_markup=main_menu(user_id)
        )
        await state.clear()
        return
    
    # Если админ в диалоге
    elif str(user_id) in [v for v in dialogs.values()]:
        user_id_str = None
        for uid, aid in dialogs.items():
            if aid == str(user_id):
                user_id_str = uid
                break
        
        if user_id_str:
            del dialogs[user_id_str]
            save_all()
            
            # Уведомляем пользователя
            await bot.send_message(
                int(user_id_str),
                "🔚 Администратор завершил диалог.\n\n"
                "Если админ был к вам невежлив, груб и т.д., нажмите «Позвать админа» и введите тег: #крип, чтобы объяснить ситуацию."
            )
            await send_main_menu(int(user_id_str))
            
            await message.answer("✅ Диалог завершён.")
            await message.answer(
                "Меню администратора:",
                reply_markup=admin_menu(user_id)
            )
            await state.clear()
            return
    
    else:
        await message.answer("❌ У вас нет активного диалога.")

# ========== КНОПКА: ПОЗВАТЬ РАНДОМНО ==========
@user_router.message(F.text == "🎲 Позвать рандомно")
async def user_call_random(message: Message):
    user_id = message.from_user.id
    
    # Проверки
    if is_banned(user_id):
        await message.answer(f"❌ Вы забанены.\nПричина: {banlist[str(user_id)]['reason']}")
        return
    
    if is_muted(user_id):
        await message.answer(f"❌ Вы в муте.")
        return
    
    if str(user_id) in dialogs:
        await message.answer("❌ У вас уже есть активный диалог.")
        return
    
    # Запрашиваем подтверждение
    await message.answer(
        "❓ Вы уверены что хотите позвать рандомного Админа?",
        reply_markup=confirm_keyboard()
    )

@user_router.message(F.text == "✅ Продолжить")
async def user_confirm_random(message: Message):
    user_id = message.from_user.id
    
    # Добавляем в очередь
    if user_id not in waiting_queue:
        waiting_queue.append(user_id)
        save_all()
    
    await message.answer(
        "⏳ Вы в очереди.",
        reply_markup=cancel_keyboard()
    )
    
    # Запускаем таймер
    asyncio.create_task(queue_timeout(user_id))
    
    # Уведомляем всех админов
    for admin_id in admins.keys():
        if not is_banned(int(admin_id)):
            try:
                await bot.send_message(
                    int(admin_id),
                    f"👤 Пользователь {get_user_name(user_id)} ищет админа."
                )
            except:
                pass

# ========== КНОПКА: ПОЗВАТЬ ПО ТЕГУ ==========
@user_router.message(F.text == "🔍 Позвать админа (по тегу)")
async def user_call_by_tag(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверки
    if is_banned(user_id):
        await message.answer(f"❌ Вы забанены.\nПричина: {banlist[str(user_id)]['reason']}")
        return
    
    if is_muted(user_id):
        await message.answer(f"❌ Вы в муте.")
        return
    
    if str(user_id) in dialogs:
        await message.answer("❌ У вас уже есть активный диалог.")
        return
    
    await state.set_state(UserStates.waiting_for_admin_tag)
    await message.answer(
        "🔍 Введите тег админа. Пример: #Дил",
        reply_markup=cancel_keyboard()
    )

@user_router.message(UserStates.waiting_for_admin_tag)
async def process_admin_tag(message: Message, state: FSMContext):
    user_id = message.from_user.id
    tag = message.text.strip()
    
    if tag == "❌ Отмена":
        await message.answer(
            "Главное меню:",
            reply_markup=main_menu(user_id)
        )
        await state.clear()
        return
    
    # Ищем админа с таким тегом
    admin_id = None
    for aid, data in admins.items():
        if data.get("tag") == tag:
            admin_id = int(aid)
            break
    
    if not admin_id:
        await message.answer("❌ Админ с таким тегом не найден.")
        await state.clear()
        return
    
    # Проверяем, не занят ли админ
    if str(admin_id) in dialogs.values():
        await message.answer("❌ Этот админ сейчас занят.")
        await state.clear()
        return
    
    # Добавляем в список ожидания по тегу
    if str(admin_id) not in pending_by_tag:
        pending_by_tag[str(admin_id)] = []
    
    if user_id not in pending_by_tag[str(admin_id)]:
        pending_by_tag[str(admin_id)].append(user_id)
        save_all()
    
    await message.answer(f"✅ Запрос отправлен админу {tag}.")
    
    # Уведомляем админа
    try:
        await bot.send_message(
            admin_id,
            f"👤 Пользователь {get_user_name(user_id)} зовёт вас в диалог (тег {tag})."
        )
    except:
        pass
    
    await state.clear()

# ========== КНОПКА: ОТМЕНА ==========
@user_router.message(F.text == "❌ Отмена")
async def user_cancel(message: Message):
    user_id = message.from_user.id
    
    # Удаляем из очереди
    if user_id in waiting_queue:
        waiting_queue.remove(user_id)
        save_all()
    
    # Возвращаем в главное меню
    await message.answer(
        "Главное меню:",
        reply_markup=main_menu(user_id)
    )
