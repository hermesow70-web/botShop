from bot import bot
import asyncio
import random
import re
from datetime import datetime, timedelta

from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from config import OWNER_ID, OWNER_TAG, CHANNEL_LINK
from database import (
    users, admins, dialogs, waiting_queue, pending_by_tag,
    banlist, mutelist, complaints, save_all,
    is_admin, is_senior_admin, is_owner, is_banned,
    get_user_name, get_admin_tag
)
from states import AdminStates
from keyboards import (
    admin_menu, admin_panel_keyboard, cancel_keyboard
)

admin_router = Router()

# ========== ПОДКЛЮЧИТЬСЯ РАНДОМНО ==========
@admin_router.message(F.text == "🎲 Подключиться рандомно")
async def admin_connect_random(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_admin(admin_id):
        return
    
    if not waiting_queue:
        await message.answer("📭 Нет пользователей в очереди.")
        return
    
    # Показываем список ожидающих
    text = "📋 Ожидающие пользователи:\n\n"
    for i, uid in enumerate(waiting_queue, 1):
        text += f"{i}. {get_user_name(uid)} (ID: {uid})\n"
    
    text += "\nВведите номер пользователя:"
    
    await state.set_state(AdminStates.waiting_for_user_id)
    await message.answer(text)

@admin_router.message(AdminStates.waiting_for_user_id)
async def process_user_id_selection(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    try:
        index = int(message.text.strip()) - 1
        if index < 0 or index >= len(waiting_queue):
            raise ValueError
        user_id = waiting_queue[index]
    except:
        await message.answer("❌ Неверный номер.")
        await state.clear()
        return
    
    # Удаляем из очереди и создаем диалог
    waiting_queue.remove(user_id)
    dialogs[str(user_id)] = str(admin_id)
    save_all()
    
    admin_tag = get_admin_tag(admin_id)
    
    # Уведомляем пользователя
    await bot.send_message(
        user_id,
        f"🔔 К вам подключился Админ {admin_tag}. Приятного общения!"
    )
    
    await message.answer(f"✅ Вы подключились к пользователю {get_user_name(user_id)}.")
    
    # Устанавливаем состояние диалога для админа
    await state.set_state(AdminStates.in_dialog)
    
    # Меню диалога
    keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔚 Завершить диалог")]],
        resize_keyboard=True
    )
    
    await message.answer(
        "Теперь вы общаетесь в этом чате. Нажмите 'Завершить диалог' чтобы закончить.",
        reply_markup=keyboard
    )

# ========== ПОДКЛЮЧИТЬСЯ ПО ТЕГУ ==========
@admin_router.message(F.text == "🔍 Подключиться по тегу")
async def admin_connect_by_tag(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_admin(admin_id):
        return
    
    if str(admin_id) not in pending_by_tag or not pending_by_tag[str(admin_id)]:
        await message.answer("📭 Нет пользователей, которые позвали вас.")
        return
    
    # Показываем список позвавших
    text = "📋 Пользователи, ожидающие вас:\n\n"
    for i, uid in enumerate(pending_by_tag[str(admin_id)], 1):
        text += f"{i}. {get_user_name(uid)} (ID: {uid})\n"
    
    text += "\nВведите номер пользователя:"
    
    await state.set_state(AdminStates.waiting_for_user_id)
    await message.answer(text)

# ========== АДМИН-ПАНЕЛЬ ==========
@admin_router.message(F.text == "👑 Админ-панель")
async def admin_panel(message: Message):
    admin_id = message.from_user.id
    
    if not is_senior_admin(admin_id) and not is_owner(admin_id):
        return
    
    await message.answer(
        "👑 Админ-панель",
        reply_markup=admin_panel_keyboard()
    )

# ========== СПИСОК ПОЛЬЗОВАТЕЛЕЙ ==========
@admin_router.message(F.text == "📋 Список пользователей")
async def list_users(message: Message):
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

# ========== СПИСОК АДМИНОВ ==========
@admin_router.message(F.text == "📋 Список админов")
async def list_admins(message: Message):
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

# ========== ВЫДАТЬ АДМИНКУ ==========
@admin_router.message(F.text == "➕ Выдать админку")
async def give_admin(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_senior_admin(admin_id) and not is_owner(admin_id):
        return
    
    await state.set_state(AdminStates.waiting_for_user_id)
    await message.answer(
        "👤 Введите ID пользователя, которому хотите выдать админку:",
        reply_markup=cancel_keyboard()
    )

@admin_router.message(AdminStates.waiting_for_user_id)
async def process_give_admin_user(message: Message, state: FSMContext):
    target_id = message.text.strip()
    
    if target_id == "❌ Отмена":
        await admin_panel(message)
        await state.clear()
        return
    
    if target_id not in users:
        await message.answer("❌ Пользователь с таким ID не найден.")
        await state.clear()
        return
    
    await state.update_data(target_admin_id=target_id)
    await state.set_state(AdminStates.waiting_for_tag)
    
    await message.answer(
        "🏷 Введите тег для админа (с #, например #Дил):",
        reply_markup=cancel_keyboard()
    )

@admin_router.message(AdminStates.waiting_for_tag)
async def process_give_admin_tag(message: Message, state: FSMContext):
    tag = message.text.strip()
    
    if tag == "❌ Отмена":
        await admin_panel(message)
        await state.clear()
        return
    
    if not tag.startswith("#"):
        await message.answer("❌ Тег должен начинаться с #")
        return
    
    # Проверяем уникальность тега
    for data in admins.values():
        if data.get("tag") == tag:
            await message.answer("❌ Такой тег уже существует.")
            return
    
    await state.update_data(admin_tag=tag)
    await state.set_state(AdminStates.waiting_for_role)
    
    # Клавиатура с ролями
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="АДМИН")],
            [KeyboardButton(text="ГЛ АДМИН")],
            [KeyboardButton(text="ТЕХ.СПЕЦИАЛИСТ")],
            [KeyboardButton(text="СОВЛАДЕЛЕЦ")],
            [KeyboardButton(text="ВЛАДЕЛЕЦ")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    
    await message.answer("👑 Выберите роль:", reply_markup=keyboard)

@admin_router.message(AdminStates.waiting_for_role)
async def process_give_admin_role(message: Message, state: FSMContext):
    role = message.text.strip()
    valid_roles = ["АДМИН", "ГЛ АДМИН", "ТЕХ.СПЕЦИАЛИСТ", "СОВЛАДЕЛЕЦ", "ВЛАДЕЛЕЦ"]
    
    if role == "❌ Отмена":
        await admin_panel(message)
        await state.clear()
        return
    
    if role not in valid_roles:
        await message.answer("❌ Выберите роль из списка.")
        return
    
    data = await state.get_data()
    target_id = data.get("target_admin_id")
    tag = data.get("admin_tag")
    
    # Выдаем админку
    admins[target_id] = {
        "tag": tag,
        "role": role,
        "issued_by": message.from_user.id,
        "date": datetime.now().isoformat()
    }
    save_all()
    
    await message.answer(f"✅ Админка выдана! ID: {target_id}, Тег: {tag}, Роль: {role}")
    
    # Уведомляем нового админа
    try:
        await bot.send_message(
            int(target_id),
            f"👑 Вам выданы права администратора!\nТег: {tag}\nРоль: {role}"
        )
    except:
        pass
    
    await admin_panel(message)
    await state.clear()

# ========== УДАЛИТЬ АДМИНА ==========
@admin_router.message(F.text == "➖ Удалить админа")
async def remove_admin(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_senior_admin(admin_id) and not is_owner(admin_id):
        return
    
    await state.set_state(AdminStates.waiting_for_remove_admin_id)
    await message.answer(
        "👤 Введите ID админа, которого хотите удалить:",
        reply_markup=cancel_keyboard()
    )

@admin_router.message(AdminStates.waiting_for_remove_admin_id)
async def process_remove_admin_id(message: Message, state: FSMContext):
    target_id = message.text.strip()
    
    if target_id == "❌ Отмена":
        await admin_panel(message)
        await state.clear()
        return
    
    if target_id not in admins:
        await message.answer("❌ Админ с таким ID не найден.")
        await state.clear()
        return
    
    # Нельзя удалить владельца
    if int(target_id) == OWNER_ID:
        await message.answer("❌ Нельзя удалить владельца.")
        await state.clear()
        return
    
    await state.update_data(remove_admin_id=target_id)
    await state.set_state(AdminStates.waiting_for_remove_admin_reason)
    
    await message.answer(
        "📝 Введите причину удаления:",
        reply_markup=cancel_keyboard()
    )

@admin_router.message(AdminStates.waiting_for_remove_admin_reason)
async def process_remove_admin_reason(message: Message, state: FSMContext):
    reason = message.text.strip()
    
    if reason == "❌ Отмена":
        await admin_panel(message)
        await state.clear()
        return
    
    data = await state.get_data()
    target_id = data.get("remove_admin_id")
    admin_tag = admins[target_id]["tag"]
    
    # Удаляем админа
    del admins[target_id]
    save_all()
    
    await message.answer(f"✅ Админ {target_id} ({admin_tag}) удалён.")
    
    # Уведомляем удаленного админа
    try:
        await bot.send_message(
            int(target_id),
            f"❌ Вы лишены прав администратора.\nПричина: {reason}"
        )
    except:
        pass
    
    await admin_panel(message)
    await state.clear()

# ========== БАН ==========
@admin_router.message(F.text == "🚫 Бан пользователя")
async def ban_user(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_senior_admin(admin_id) and not is_owner(admin_id):
        return
    
    await state.set_state(AdminStates.waiting_for_ban_reason)
    await message.answer(
        "👤 Введите ID пользователя для бана:",
        reply_markup=cancel_keyboard()
    )

@admin_router.message(AdminStates.waiting_for_ban_reason)
async def process_ban_id(message: Message, state: FSMContext):
    target_id = message.text.strip()
    
    if target_id == "❌ Отмена":
        await admin_panel(message)
        await state.clear()
        return
    
    if target_id not in users:
        await message.answer("❌ Пользователь с таким ID не найден.")
        await state.clear()
        return
    
    # Нельзя забанить старших админов
    if target_id in admins:
        if is_senior_admin(int(target_id)) or int(target_id) == OWNER_ID:
            await message.answer("❌ Нельзя забанить старшего администратора или владельца.")
            await state.clear()
            return
    
    await state.update_data(ban_target_id=target_id)
    await state.set_state(AdminStates.waiting_for_ban_reason)
    
    await message.answer(
        "📝 Введите причину бана:",
        reply_markup=cancel_keyboard()
    )

@admin_router.message(AdminStates.waiting_for_ban_reason)
async def process_ban_reason(message: Message, state: FSMContext):
    reason = message.text.strip()
    
    if reason == "❌ Отмена":
        await admin_panel(message)
        await state.clear()
        return
    
    data = await state.get_data()
    target_id = data.get("ban_target_id")
    
    # Баним
    banlist[target_id] = {
        "reason": reason,
        "date": datetime.now().isoformat(),
        "banned_by": message.from_user.id
    }
    
    # Если был в диалоге — завершаем
    if target_id in dialogs:
        admin_id = dialogs[target_id]
        del dialogs[target_id]
        try:
            await bot.send_message(
                int(admin_id),
                "🔚 Пользователь забанен, диалог завершён."
            )
        except:
            pass
    
    save_all()
    
    await message.answer(f"✅ Пользователь {target_id} забанен.\nПричина: {reason}")
    
    # Уведомляем пользователя
    try:
        await bot.send_message(
            int(target_id),
            f"🚫 Вы забанены.\nПричина: {reason}"
        )
    except:
        pass
    
    await admin_panel(message)
    await state.clear()

# ========== РАЗБАН ==========
@admin_router.message(F.text == "✅ Разбан")
async def unban_user(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_senior_admin(admin_id) and not is_owner(admin_id):
        return
    
    await state.set_state(AdminStates.waiting_for_unban_user)
    await message.answer(
        "👤 Введите ID пользователя для разбана:",
        reply_markup=cancel_keyboard()
    )

@admin_router.message(AdminStates.waiting_for_unban_user)
async def process_unban(message: Message, state: FSMContext):
    target_id = message.text.strip()
    
    if target_id == "❌ Отмена":
        await admin_panel(message)
        await state.clear()
        return
    
    if target_id not in banlist:
        await message.answer("❌ Этот пользователь не в бане.")
        await state.clear()
        return
    
    # Разбаниваем
    del banlist[target_id]
    save_all()
    
    await message.answer(f"✅ Пользователь {target_id} разбанен.")
    
    # Уведомляем пользователя
    try:
        await bot.send_message(
            int(target_id),
            "✅ Вы разбанены. Можете снова пользоваться ботом."
        )
    except:
        pass
    
    await admin_panel(message)
    await state.clear()

# ========== МУТ ==========
@admin_router.message(F.text == "🔇 Мут")
async def mute_user(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_senior_admin(admin_id) and not is_owner(admin_id):
        return
    
    await state.set_state(AdminStates.waiting_for_ban_reason)
    await message.answer(
        "👤 Введите ID пользователя для мута:",
        reply_markup=cancel_keyboard()
    )

@admin_router.message(AdminStates.waiting_for_ban_reason)
async def process_mute_id(message: Message, state: FSMContext):
    target_id = message.text.strip()
    
    if target_id == "❌ Отмена":
        await admin_panel(message)
        await state.clear()
        return
    
    if target_id not in users:
        await message.answer("❌ Пользователь с таким ID не найден.")
        await state.clear()
        return
    
    # Нельзя замутить старших админов
    if target_id in admins:
        if is_senior_admin(int(target_id)) or int(target_id) == OWNER_ID:
            await message.answer("❌ Нельзя замутить старшего администратора или владельца.")
            await state.clear()
            return
    
    await state.update_data(mute_target_id=target_id)
    await state.set_state(AdminStates.waiting_for_mute_time)
    
    await message.answer(
        "⏱ Введите время мута в минутах (0 - бессрочно):",
        reply_markup=cancel_keyboard()
    )

@admin_router.message(AdminStates.waiting_for_mute_time)
async def process_mute_time(message: Message, state: FSMContext):
    try:
        minutes = int(message.text.strip())
    except:
        if message.text == "❌ Отмена":
            await admin_panel(message)
            await state.clear()
            return
        await message.answer("❌ Введите число минут.")
        return
    
    data = await state.get_data()
    target_id = data.get("mute_target_id")
    
    if minutes == 0:
        mute_until = datetime.now() + timedelta(days=365*10)  # ~10 лет
    else:
        mute_until = datetime.now() + timedelta(minutes=minutes)
    
    # Мутим
    mutelist[target_id] = {
        "until": mute_until.isoformat(),
        "reason": "Мут от администратора",
        "muted_by": message.from_user.id
    }
    save_all()
    
    time_str = "бессрочно" if minutes == 0 else f"{minutes} минут"
    await message.answer(f"✅ Пользователь {target_id} замучен на {time_str}.")
    
    # Уведомляем пользователя
    try:
        await bot.send_message(
            int(target_id),
            f"🔇 Вы замучены на {time_str}."
        )
    except:
        pass
    
    await admin_panel(message)
    await state.clear()

# ========== РАЗМУТ ==========
@admin_router.message(F.text == "🔊 Размут")
async def unmute_user(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_senior_admin(admin_id) and not is_owner(admin_id):
        return
    
    await state.set_state(AdminStates.waiting_for_unmute_user)
    await message.answer(
        "👤 Введите ID пользователя для размута:",
        reply_markup=cancel_keyboard()
    )

@admin_router.message(AdminStates.waiting_for_unmute_user)
async def process_unmute(message: Message, state: FSMContext):
    target_id = message.text.strip()
    
    if target_id == "❌ Отмена":
        await admin_panel(message)
        await state.clear()
        return
    
    if target_id not in mutelist:
        await message.answer("❌ Этот пользователь не в муте.")
        await state.clear()
        return
    
    # Размучиваем
    del mutelist[target_id]
    save_all()
    
    await message.answer(f"✅ Пользователь {target_id} размучен.")
    
    # Уведомляем пользователя
    try:
        await bot.send_message(
            int(target_id),
            "🔊 Вы размучены. Можете снова писать."
        )
    except:
        pass
    
    await admin_panel(message)
    await state.clear()

# ========== ЖАЛОБЫ ==========
@admin_router.message(F.text == "⚠️ Жалобы (#крип)")
async def show_complaints(message: Message):
    admin_id = message.from_user.id
    
    if not is_senior_admin(admin_id) and not is_owner(admin_id):
        return
    
    if not complaints:
        await message.answer("📭 Нет жалоб.")
        return
    
    text = "⚠️ **Жалобы:**\n\n"
    for cid, data in list(complaints.items())[-10:]:
        text += f"ID: {cid}\n"
        text += f"От: {data['user_name']} (ID: {data['user_id']})\n"
        text += f"На админа: {data['admin_tag']}\n"
        text += f"Текст: {data['text']}\n"
        text += f"Дата: {data['date'][:19]}\n\n"
    
    await message.answer(text)

# ========== РАССЫЛКА ==========
@admin_router.message(F.text == "📢 Рассылка")
async def broadcast_start(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    if not is_senior_admin(admin_id) and not is_owner(admin_id):
        return
    
    await state.set_state(AdminStates.waiting_for_broadcast_text)
    await message.answer(
        "📝 Введите текст рассылки:",
        reply_markup=cancel_keyboard()
    )

@admin_router.message(AdminStates.waiting_for_broadcast_text)
async def broadcast_text(message: Message, state: FSMContext):
    text = message.text.strip()
    
    if text == "❌ Отмена":
        await admin_panel(message)
        await state.clear()
        return
    
    await state.update_data(broadcast_text=text)
    await state.set_state(AdminStates.waiting_for_broadcast_button)
    
    # Клавиатура с вариантами
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="-")],
            [KeyboardButton(text="❌ Отмена")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "🔗 Добавить кнопку?\n"
        "Формат: Текст кнопки | URL\n"
        "Или отправьте '-' чтобы пропустить",
        reply_markup=keyboard
    )

@admin_router.message(AdminStates.waiting_for_broadcast_button)
async def broadcast_button(message: Message, state: FSMContext):
    button_data = message.text.strip()
    
    if button_data == "❌ Отмена":
        await admin_panel(message)
        await state.clear()
        return
    
    data = await state.get_data()
    broadcast_text = data.get("broadcast_text")
    
    keyboard = None
    if button_data != "-":
        try:
            btn_text, url = button_data.split("|")
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text=btn_text.strip(), url=url.strip())]]
            )
        except:
            await message.answer("❌ Неправильный формат. Используйте: Текст | URL")
            return
    
    await message.answer("⏳ Начинаю рассылку...")
    
    sent = 0
    failed = 0
    
    # Рассылаем всем пользователям и админам
    for uid in list(users.keys()) + list(admins.keys()):
        if uid in banlist:
            failed += 1
            continue
        
        try:
            await bot.send_message(
                int(uid),
                broadcast_text,
                reply_markup=keyboard
            )
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    await message.answer(f"✅ Рассылка завершена!\nОтправлено: {sent}\nНе доставлено: {failed}")
    await admin_panel(message)
    await state.clear()

# ========== НАЗАД ==========
@admin_router.message(F.text == "◀️ Назад")
async def back_to_admin_menu(message: Message):
    admin_id = message.from_user.id
    
    if is_senior_admin(admin_id) or is_owner(admin_id):
        await admin_panel(message)
    else:
        await message.answer(
            "Меню администратора:",
            reply_markup=admin_menu(admin_id)
        )
