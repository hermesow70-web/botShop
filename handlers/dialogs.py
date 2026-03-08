from bot import bot
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from database import dialogs, save_all, get_admin_tag, get_user_name
from keyboards import main_menu, admin_menu
from states import UserStates, AdminStates

dialog_router = Router()

# ========== ДИАЛОГИ ОТ АДМИНА ==========
@dialog_router.message(AdminStates.in_dialog)
async def admin_dialog_message(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    
    # Ищем пользователя в диалоге
    user_id = None
    for uid, aid in dialogs.items():
        if aid == str(admin_id):
            user_id = int(uid)
            break
    
    if not user_id:
        await message.answer("❌ Диалог не найден.")
        await state.clear()
        await message.answer(
            "Меню администратора:",
            reply_markup=admin_menu(admin_id)
        )
        return
    
    # Если админ нажал "Завершить диалог"
    if message.text == "🔚 Завершить диалог":
        del dialogs[str(user_id)]
        save_all()
        
        await bot.send_message(
            user_id,
            "🔚 Администратор завершил диалог.\n\n"
            "Если админ был к вам невежлив, груб и т.д., нажмите «Позвать админа» и введите тег: #крип, чтобы объяснить ситуацию."
        )
        await send_main_menu(user_id)
        
        await message.answer("✅ Диалог завершён.")
        await message.answer(
            "Меню администратора:",
            reply_markup=admin_menu(admin_id)
        )
        await state.clear()
        return
    
    # Пересылаем сообщение пользователю с тегом админа
    admin_tag = get_admin_tag(admin_id)
    await bot.send_message(
        user_id,
        f"{admin_tag}\n{message.text}"
    )

# ========== ДИАЛОГИ ОТ ПОЛЬЗОВАТЕЛЯ ==========
@dialog_router.message(UserStates.in_dialog)
async def user_dialog_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    # Проверяем, есть ли диалог
    if str(user_id) not in dialogs:
        await message.answer("❌ Диалог не найден.")
        await state.clear()
        await message.answer(
            "Главное меню:",
            reply_markup=main_menu(user_id)
        )
        return
    
    admin_id = int(dialogs[str(user_id)])
    
    # Если пользователь нажал "Завершить диалог"
    if message.text == "🔚 Завершить диалог":
        del dialogs[str(user_id)]
        save_all()
        
        await bot.send_message(
            admin_id,
            "🔚 Пользователь завершил диалог.",
            reply_markup=admin_menu(admin_id)
        )
        
        await message.answer(
            "✅ Диалог завершён.\n\n"
            "Если админ был к вам невежлив, груб и т.д., нажмите «Позвать админа» и введите тег: #крип, чтобы объяснить ситуацию."
        )
        await message.answer(
            "Главное меню:",
            reply_markup=main_menu(user_id)
        )
        await state.clear()
        return
    
    # Пересылаем сообщение админу с именем пользователя
    user_name = get_user_name(user_id)
    await bot.send_message(
        admin_id,
        f"{user_name}\n{message.text}"
    )
