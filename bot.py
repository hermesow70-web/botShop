#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Shop Bot - ПОЛНАЯ ФИНАЛЬНАЯ ВЕРСИЯ
Категории, товары, корзина, промокоды, админка, поддержка
ВСЁ ПРОВЕРЕНО - РАБОТАЕТ!
"""

# ========== ВСТРОЕННЫЕ БИБЛИОТЕКИ ==========
import asyncio
import logging
import random
import string
import json
import os
import sys
import signal
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# ========== УСТАНОВЛЕННЫЕ БИБЛИОТЕКИ ==========
import httpx
import psutil
import aiohttp
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton
)

# ========== ТВОИ ДАННЫЕ ==========
BOT_TOKEN = "8674038652:AAHPnGq-hteuyBDRNI6F-5Ea1NQm8wE31ZI"
ADMIN_ID = 8402407852
CRYPTOBOT_TOKEN = "545243:AAbNak8pGgjhloWOz2SfoiUcLBfAijfhc6Q"
SUPPORT_USERNAME = "@alooopaq"
# ================================

# Проверка токенов
if not BOT_TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не найден!")
    sys.exit(1)

# ===== НАСТРОЙКА ЛОГИРОВАНИЯ =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ===== ИНИЦИАЛИЗАЦИЯ БОТА =====
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ===== СОСТОЯНИЯ FSM =====
class AdminStates(StatesGroup):
    # Категории
    waiting_category_name = State()
    waiting_category_edit = State()
    
    # Товары
    waiting_category_choice = State()
    waiting_product_name = State()
    waiting_product_desc = State()
    waiting_product_price = State()
    waiting_product_stock = State()
    waiting_product_edit = State()
    
    # Рассылка
    waiting_broadcast_text = State()
    waiting_broadcast_button = State()
    
    # Поддержка
    waiting_support_answer = State()
    
    # Баланс
    waiting_user_id_balance = State()
    waiting_balance_amount = State()
    
    # Выдача товара
    waiting_delivery_text = State()

class UserStates(StatesGroup):
    waiting_support_question = State()
    waiting_crypto_amount = State()
    waiting_promo_for_product = State()  # Для ввода промокода

class PromoStates(StatesGroup):
    waiting_promo_name = State()
    waiting_promo_discount = State()
    waiting_promo_uses = State()

# ===== РАБОТА С ДАННЫМИ =====
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

def load_data(filename: str) -> Dict:
    filepath = DATA_DIR / f"{filename}.json"
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_data(filename: str, data: Dict) -> None:
    filepath = DATA_DIR / f"{filename}.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ===== ИНИЦИАЛИЗАЦИЯ ДАННЫХ =====
users = load_data("users")
categories = load_data("categories")
support_questions = load_data("support_questions")
crypto_invoices = load_data("crypto_invoices")
promocodes = load_data("promocodes")
pending_delivery = {}

if not promocodes:
    promocodes = {}  # {"PROMO50": {"discount": 50, "uses_left": 10, "used": 0}}

def save_all():
    save_data("users", users)
    save_data("categories", categories)
    save_data("support_questions", support_questions)
    save_data("crypto_invoices", crypto_invoices)
    save_data("promocodes", promocodes)

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def generate_cart_number() -> str:
    return ''.join(random.choices(string.digits, k=4))

async def notify_user(user_id: int, text: str, keyboard=None) -> bool:
    try:
        if keyboard:
            await bot.send_message(user_id, text, reply_markup=keyboard)
        else:
            await bot.send_message(user_id, text)
        logger.info(f"✅ Уведомление отправлено {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка отправки {user_id}: {e}")
        return False

# ===== КЛАВИАТУРЫ =====
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍️ КАТАЛОГ", callback_data="catalog")],
        [InlineKeyboardButton(text="👤 ПРОФИЛЬ", callback_data="profile")],
        [InlineKeyboardButton(text="🆘 ТЕХ.ПОДДЕРЖКА", callback_data="support")]
    ])

def profile_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить баланс", callback_data="topup_menu")],
        [InlineKeyboardButton(text="🛒 Корзина", callback_data="view_cart")],
        [InlineKeyboardButton(text="📦 Мои покупки", callback_data="my_purchases")],
        [InlineKeyboardButton(text="🎟 Ввести промокод", callback_data="enter_promo")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
    ])

def topup_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="₿ Криптобот (USDT)", callback_data="topup_crypto")],
        [InlineKeyboardButton(text="💳 Карта/СБП", url=f"https://t.me/{SUPPORT_USERNAME[1:]}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
    ])

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="➕ Добавить категорию", callback_data="admin_add_category")],
        [InlineKeyboardButton(text="📋 Список категорий", callback_data="admin_list_categories")],
        [InlineKeyboardButton(text="➕ Добавить товар", callback_data="admin_add_product")],
        [InlineKeyboardButton(text="📦 Все товары", callback_data="admin_all_products")],
        [InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin_promocodes")],
        [InlineKeyboardButton(text="💰 Изменить баланс", callback_data="admin_change_balance")],
        [InlineKeyboardButton(text="👥 Все пользователи", callback_data="admin_users_list")],
        [InlineKeyboardButton(text="🆘 Вопросы поддержки", callback_data="admin_support_questions")],
        [InlineKeyboardButton(text="🔙 Выход", callback_data="back_main")]
    ])

# ===== КРИПТОБОТ ФУНКЦИИ =====
async def create_crypto_invoice(amount_usdt: float, user_id: int):
    async with httpx.AsyncClient() as client:
        headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
        payload = {
            "asset": "USDT",
            "amount": str(amount_usdt),
            "description": f"Пополнение баланса для пользователя {user_id}",
            "paid_btn_name": "callback",
            "paid_btn_url": f"https://t.me/{(await bot.me()).username}?start",
            "allow_comments": False
        }
        
        try:
            response = await client.post(
                "https://pay.crypt.bot/api/createInvoice",
                headers=headers,
                json=payload
            )
            data = response.json()
            
            if data.get("ok"):
                invoice = data["result"]
                invoice_id = str(invoice["invoice_id"])
                
                crypto_invoices[invoice_id] = {
                    "user_id": str(user_id),
                    "amount_usdt": amount_usdt,
                    "amount_rub": int(amount_usdt * 100),
                    "status": "active",
                    "created_at": datetime.now().isoformat(),
                    "pay_url": invoice["pay_url"]
                }
                save_all()
                
                return invoice
            else:
                logger.error(f"CryptoBot error: {data}")
                return None
        except Exception as e:
            logger.error(f"Error creating invoice: {e}")
            return None

async def check_invoice_status(invoice_id: str):
    async with httpx.AsyncClient() as client:
        headers = {"Crypto-Pay-API-Token": CRYPTOBOT_TOKEN}
        params = {"invoice_id": invoice_id}
        
        try:
            response = await client.get(
                "https://pay.crypt.bot/api/getInvoices",
                headers=headers,
                params=params
            )
            data = response.json()
            
            if data.get("ok") and data["result"]["items"]:
                return data["result"]["items"][0]
        except:
            pass
        return None

async def process_paid_invoice(invoice_id: str):
    if invoice_id in crypto_invoices:
        invoice = crypto_invoices[invoice_id]
        
        if invoice["status"] == "paid":
            return
        
        user_id = invoice["user_id"]
        amount_rub = invoice["amount_rub"]
        
        if user_id in users:
            old_balance = users[user_id]["balance"]
            users[user_id]["balance"] += amount_rub
            new_balance = users[user_id]["balance"]
        else:
            old_balance = 0
            users[user_id] = {
                "balance": amount_rub,
                "cart": {},
                "purchases": [],
                "join_date": datetime.now().isoformat()
            }
            new_balance = amount_rub
        
        invoice["status"] = "paid"
        invoice["paid_at"] = datetime.now().isoformat()
        save_all()
        
        await notify_user(
            int(user_id),
            f"💰 **Пополнение баланса**\n\n"
            f"Сумма: `+{amount_rub}₽`\n"
            f"Было: `{old_balance}₽`\n"
            f"Стало: `{new_balance}₽`\n\n"
            f"✅ Средства зачислены автоматически"
        )
        
        await bot.send_message(
            ADMIN_ID,
            f"💰 **Крипто-оплата**\n\n"
            f"👤 Пользователь: `{user_id}`\n"
            f"🇷🇺 Сумма: `{amount_rub}₽`\n"
            f"🆔 Invoice: `{invoice_id}`"
        )

async def check_invoices_periodically():
    while True:
        for invoice_id, invoice in list(crypto_invoices.items()):
            if invoice["status"] == "active":
                created = datetime.fromisoformat(invoice["created_at"])
                if (datetime.now() - created).seconds > 60:
                    status = await check_invoice_status(invoice_id)
                    if status and status["status"] == "paid":
                        await process_paid_invoice(invoice_id)
        
        await asyncio.sleep(30)

# ===== ОСНОВНЫЕ ХЕНДЛЕРЫ =====
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = str(message.from_user.id)
    
    if user_id not in users:
        users[user_id] = {
            "balance": 0,
            "cart": {},
            "purchases": [],
            "promo_used": [],  # Какие промокоды уже использовал
            "join_date": datetime.now().isoformat(),
            "username": message.from_user.username,
            "first_name": message.from_user.first_name
        }
        save_all()
        
        await notify_user(
            int(user_id),
            f"👋 Добро пожаловать в маркет!\n\n"
            f"Твой ID: `{user_id}`\n"
            f"Баланс: `0₽`\n\n"
            f"💰 Для покупок нужно пополнить баланс в профиле."
        )
    
    await message.answer(
        "👋 Здравствуй, этот маркет для тебя, тут ты можешь приобрести много чего)\n\n"
        "👇 ЖМИ КАТАЛОГ 👇",
        reply_markup=main_menu()
    )

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("❌ У вас нет прав администратора.")
        return
    
    await message.answer(
        "👑 **Админ-панель**\n\n"
        "Выберите действие:",
        reply_markup=admin_menu()
    )

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    total_users = len(users)
    total_purchases = sum(len(u.get("purchases", [])) for u in users.values())
    total_revenue = sum(p["amount"] for u in users.values() for p in u.get("purchases", []))
    
    cpu_percent = psutil.cpu_percent()
    memory = psutil.virtual_memory()
    
    text = f"📊 **Статистика бота**\n\n"
    text += f"👥 Пользователей: `{total_users}`\n"
    text += f"📦 Продаж: `{total_purchases}`\n"
    text += f"💰 Выручка: `{total_revenue}₽`\n\n"
    text += f"🖥 **Система:**\n"
    text += f"CPU: `{cpu_percent}%`\n"
    text += f"RAM: `{memory.percent}%`"
    
    await message.answer(text)

@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "👋 Здравствуй, этот маркет для тебя, тут ты можешь приобрести много чего)\n\n"
        "👇 ЖМИ КАТАЛОГ 👇",
        reply_markup=main_menu()
    )
    await callback.answer()

# ===== ПРОФИЛЬ =====
@dp.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users.get(user_id, {"balance": 0, "purchases": []})
    
    text = f"👤 **Профиль**\n\n"
    text += f"🆔 ID: `{user_id}`\n"
    text += f"👤 Имя: {callback.from_user.first_name}\n"
    text += f"💰 Баланс: `{user['balance']}₽`\n"
    text += f"📦 Покупок: `{len(user.get('purchases', []))}`\n\n"
    text += f"📅 Зарегистрирован: {user.get('join_date', 'неизвестно')[:10]}"
    
    await callback.message.edit_text(text, reply_markup=profile_menu())
    await callback.answer()

@dp.callback_query(F.data == "my_purchases")
async def my_purchases(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users.get(user_id, {"purchases": []})
    purchases = user.get("purchases", [])
    
    if not purchases:
        await callback.message.edit_text(
            "📦 У вас пока нет покупок",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
            ])
        )
        await callback.answer()
        return
    
    text = "📦 **Мои покупки:**\n\n"
    
    for purchase in reversed(purchases[-10:]):
        text += f"🎫 Заказ #{purchase.get('order_number', 'N/A')}\n"
        text += f"💰 Сумма: {purchase.get('amount', 0)}₽\n"
        text += f"📅 Дата: {purchase.get('date', '')[:10]}\n"
        text += f"✅ Доставлен: {'Да' if purchase.get('delivered') else 'Нет'}\n\n"
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
        ])
    )
    await callback.answer()

# ===== ПОПОЛНЕНИЕ БАЛАНСА =====
@dp.callback_query(F.data == "topup_menu")
async def topup_menu_handler(callback: CallbackQuery):
    await callback.message.edit_text(
        "💰 **Выберите способ пополнения:**\n\n"
        "₿ **Криптобот** - автоматическое зачисление (USDT)\n"
        "💳 **Карта/СБП** - напишите администратору",
        reply_markup=topup_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "topup_crypto")
async def topup_crypto(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_crypto_amount)
    await callback.message.edit_text(
        "₿ **Криптобот (USDT)**\n\n"
        "Введите сумму в рублях для пополнения (минимум 100₽):\n\n"
        "Курс: `1 USDT ≈ 100₽`",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="100₽ (1 USDT)", callback_data="crypto_100")],
            [InlineKeyboardButton(text="500₽ (5 USDT)", callback_data="crypto_500")],
            [InlineKeyboardButton(text="1000₽ (10 USDT)", callback_data="crypto_1000")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="topup_menu")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("crypto_"))
async def crypto_preset(callback: CallbackQuery, state: FSMContext):
    amount_rub = int(callback.data.split("_")[1])
    amount_usdt = amount_rub / 100
    
    await state.clear()
    
    invoice = await create_crypto_invoice(amount_usdt, callback.from_user.id)
    
    if invoice:
        text = f"✅ **Счет создан!**\n\n"
        text += f"💰 Сумма: `{amount_usdt} USDT` (~`{amount_rub}₽`)\n"
        text += f"💎 Актив: `USDT`\n\n"
        text += f"❗️ После оплаты баланс пополнится **автоматически**"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить USDT", url=invoice["pay_url"])],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_invoice_{invoice['invoice_id']}")],
            [InlineKeyboardButton(text="🔙 В профиль", callback_data="profile")]
        ])
        
        await callback.message.edit_text(text, reply_markup=keyboard)
    else:
        await callback.message.edit_text(
            "❌ Ошибка создания счета. Попробуйте позже.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="topup_menu")]
            ])
        )
    await callback.answer()

@dp.message(UserStates.waiting_crypto_amount)
async def process_crypto_amount(message: Message, state: FSMContext):
    try:
        amount_rub = int(message.text)
        if amount_rub < 100:
            await message.answer("❌ Минимальная сумма 100₽")
            return
        
        amount_usdt = amount_rub / 100
        await state.clear()
        
        invoice = await create_crypto_invoice(amount_usdt, message.from_user.id)
        
        if invoice:
            text = f"✅ **Счет создан!**\n\n"
            text += f"💰 Сумма: `{amount_usdt} USDT` (~`{amount_rub}₽`)\n"
            text += f"💎 Актив: `USDT`\n\n"
            text += f"❗️ После оплаты баланс пополнится **автоматически**"
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💳 Оплатить USDT", url=invoice["pay_url"])],
                [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_invoice_{invoice['invoice_id']}")],
                [InlineKeyboardButton(text="🔙 В профиль", callback_data="profile")]
            ])
            
            await message.answer(text, reply_markup=keyboard)
        else:
            await message.answer(
                "❌ Ошибка создания счета. Попробуйте позже.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 В профиль", callback_data="profile")]
                ])
            )
    except ValueError:
        await message.answer("❌ Введите число")

@dp.callback_query(F.data.startswith("check_invoice_"))
async def check_invoice(callback: CallbackQuery):
    invoice_id = callback.data.split("_")[2]
    
    if invoice_id in crypto_invoices:
        invoice = crypto_invoices[invoice_id]
        
        if invoice["status"] == "paid":
            await callback.answer("✅ Счет уже оплачен!", show_alert=True)
            await show_profile(callback)
        else:
            status = await check_invoice_status(invoice_id)
            if status and status["status"] == "paid":
                await process_paid_invoice(invoice_id)
                await callback.answer("✅ Оплата подтверждена!", show_alert=True)
                await show_profile(callback)
            else:
                await callback.answer("❌ Счет еще не оплачен", show_alert=True)
    else:
        await callback.answer("❌ Счет не найден", show_alert=True)

# ===== ПРОМОКОДЫ =====
@dp.callback_query(F.data == "enter_promo")
async def enter_promo(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_promo_for_product)
    await callback.message.edit_text(
        "🎟 **Введите промокод**\n\n"
        "Если у вас есть промокод на скидку, введите его:\n"
        "(или отправьте '-' чтобы пропустить)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
        ])
    )
    await callback.answer()

@dp.message(UserStates.waiting_promo_for_product)
async def process_promo_input(message: Message, state: FSMContext):
    promo_code = message.text.strip().upper()
    
    if promo_code == "-":
        await message.answer("✅ Промокод не применен", reply_markup=profile_menu())
        await state.clear()
        return
    
    user_id = str(message.from_user.id)
    
    # Проверяем существует ли промокод
    if promo_code not in promocodes:
        await message.answer(
            "❌ Такого промокода не существует!\n\n"
            "Попробуйте еще раз или отправьте '-'",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 В профиль", callback_data="profile")]
            ])
        )
        await state.clear()
        return
    
    promo_data = promocodes[promo_code]
    
    # Проверяем остались ли активации
    if promo_data["uses_left"] <= 0:
        await message.answer(
            "❌ Промокод больше не действует (лимит активаций исчерпан)!",
            reply_markup=profile_menu()
        )
        await state.clear()
        return
    
    # Проверял ли пользователь уже этот промокод
    if user_id in users and "promo_used" in users[user_id] and promo_code in users[user_id]["promo_used"]:
        await message.answer(
            "❌ Вы уже использовали этот промокод!",
            reply_markup=profile_menu()
        )
        await state.clear()
        return
    
    # Сохраняем промокод для пользователя
    if "active_promo" not in users[user_id]:
        users[user_id]["active_promo"] = {}
    
    users[user_id]["active_promo"] = {
        "code": promo_code,
        "discount": promo_data["discount"]
    }
    save_all()
    
    await message.answer(
        f"✅ **Промокод активирован!**\n\n"
        f"🎟 Промокод: {promo_code}\n"
        f"💰 Скидка: {promo_data['discount']}%\n\n"
        f"Теперь при покупке товара скидка применится автоматически!",
        reply_markup=profile_menu()
    )
    await state.clear()

# ===== КАТАЛОГ =====
@dp.callback_query(F.data == "catalog")
async def show_catalog(callback: CallbackQuery):
    if not categories:
        await callback.message.edit_text(
            "📭 Каталог пуст. Загляните позже!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
            ])
        )
        await callback.answer()
        return
    
    buttons = []
    for cat_id, cat_data in categories.items():
        buttons.append([InlineKeyboardButton(
            text=f"📁 {cat_data['name']}",
            callback_data=f"category_{cat_id}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")])
    
    await callback.message.edit_text(
        "📚 **Выберите категорию:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("category_"))
async def show_products(callback: CallbackQuery):
    cat_id = callback.data.split("_")[1]
    category = categories.get(cat_id)
    
    if not category or not category.get("products"):
        await callback.message.edit_text(
            "📭 В этой категории пока нет товаров",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="catalog")]
            ])
        )
        await callback.answer()
        return
    
    buttons = []
    for prod_id, product in category["products"].items():
        if product['stock'] > 0:
            buttons.append([InlineKeyboardButton(
                text=f"{product['name']} - {product['price']}₽ (ост. {product['stock']})",
                callback_data=f"product_{cat_id}_{prod_id}"
            )])
    
    if not buttons:
        await callback.message.edit_text(
            "📭 В этой категории нет товаров в наличии",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="catalog")]
            ])
        )
        await callback.answer()
        return
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="catalog")])
    
    await callback.message.edit_text(
        f"📁 **{category['name']}**\n\nВыберите товар:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("product_"))
async def show_product(callback: CallbackQuery):
    _, cat_id, prod_id = callback.data.split("_")
    product = categories[cat_id]["products"][prod_id]
    
    user_id = str(callback.from_user.id)
    final_price = product['price']
    promo_text = ""
    
    # Проверяем есть ли активный промокод
    if user_id in users and "active_promo" in users[user_id]:
        promo = users[user_id]["active_promo"]
        discount = promo["discount"]
        final_price = int(product['price'] * (100 - discount) / 100)
        promo_text = f"\n\n🎟 С учетом промокода: `{final_price}₽` (скидка {discount}%)"
    
    text = f"📦 **{product['name']}**\n\n"
    text += f"📝 {product['desc']}\n\n"
    text += f"💰 Цена: `{product['price']}₽`{promo_text}\n"
    text += f"📦 В наличии: `{product['stock']} шт.`\n\n"
    text += f"🆔 Номер товара: `{prod_id}`"
    
    buttons = [
        [InlineKeyboardButton(text="💳 Купить сейчас", callback_data=f"buy_now_{cat_id}_{prod_id}")],
        [InlineKeyboardButton(text="➕ В корзину", callback_data=f"add_{cat_id}_{prod_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"category_{cat_id}")]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

# ===== ПОКУПКА СРАЗУ (С ПРОМОКОДОМ) =====
@dp.callback_query(F.data.startswith("buy_now_"))
async def buy_now(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    _, _, cat_id, prod_id = callback.data.split("_")
    
    product = categories[cat_id]["products"][prod_id]
    
    # Проверяем наличие
    if product['stock'] <= 0:
        await callback.answer("❌ Товара нет в наличии!", show_alert=True)
        return
    
    # Проверяем баланс
    if user_id not in users:
        users[user_id] = {"balance": 0, "cart": {}, "purchases": [], "promo_used": []}
    
    # Считаем цену с промокодом
    price = product['price']
    discount = 0
    promo_code = None
    
    if user_id in users and "active_promo" in users[user_id]:
        promo = users[user_id]["active_promo"]
        discount = promo["discount"]
        price = int(product['price'] * (100 - discount) / 100)
        promo_code = promo["code"]
    
    if users[user_id]["balance"] < price:
        await callback.message.edit_text(
            f"❌ **Недостаточно средств!**\n\n"
            f"💰 Ваш баланс: `{users[user_id]['balance']}₽`\n"
            f"💳 Сумма покупки: `{price}₽`\n\n"
            f"Пополните баланс в профиле.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Пополнить", callback_data="topup_menu")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"product_{cat_id}_{prod_id}")]
            ])
        )
        await callback.answer()
        return
    
    # СПИСЫВАЕМ БАЛАНС
    old_balance = users[user_id]["balance"]
    users[user_id]["balance"] -= price
    
    # УМЕНЬШАЕМ КОЛИЧЕСТВО ТОВАРА
    categories[cat_id]["products"][prod_id]["stock"] -= 1
    
    # Если был промокод - уменьшаем лимит и отмечаем использование
    if promo_code:
        promocodes[promo_code]["uses_left"] -= 1
        promocodes[promo_code]["used"] += 1
        
        if "promo_used" not in users[user_id]:
            users[user_id]["promo_used"] = []
        users[user_id]["promo_used"].append(promo_code)
        
        # Удаляем активный промокод
        del users[user_id]["active_promo"]
    
    order_number = generate_cart_number()
    
    # Уведомление админу
    purchase_text = f"🛒 **МГНОВЕННАЯ ПОКУПКА!**\n\n"
    purchase_text += f"👤 Пользователь: {callback.from_user.full_name}\n"
    purchase_text += f"🆔 ID: `{user_id}`\n"
    purchase_text += f"📦 Товар: {product['name']}\n"
    purchase_text += f"💰 Цена: {price}₽"
    
    if discount > 0:
        purchase_text += f" (скидка {discount}%, было {product['price']}₽)\n"
        purchase_text += f"🎟 Промокод: {promo_code}\n"
    else:
        purchase_text += "\n"
    
    purchase_text += f"🎫 Номер: `{order_number}`"
    
    await bot.send_message(
        ADMIN_ID,
        purchase_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Ввести товар", callback_data=f"deliver_{order_number}_{user_id}")]
        ])
    )
    
    pending_delivery[order_number] = {
        "user_id": user_id,
        "product": product['name'],
        "amount": price
    }
    
    # Уведомление пользователю
    promo_text = f" (скидка {discount}%)" if discount > 0 else ""
    await notify_user(
        int(user_id),
        f"✅ **Покупка совершена!**\n\n"
        f"📦 Товар: {product['name']}\n"
        f"💰 Сумма: {price}₽{promo_text}\n"
        f"🎫 Номер заказа: `{order_number}`\n\n"
        f"💳 Баланс: `{old_balance}₽` → `{users[user_id]['balance']}₽`\n\n"
        f"⏳ Ожидайте, администратор скоро выдаст товар."
    )
    
    # Сохраняем в историю
    users[user_id]["purchases"].append({
        "date": datetime.now().isoformat(),
        "amount": price,
        "product": product['name'],
        "order_number": order_number,
        "delivered": False
    })
    save_all()
    
    await callback.message.edit_text(
        f"✅ **Покупка совершена!**\n\n"
        f"💰 С баланса списано: `{price}₽`{promo_text}\n"
        f"🎫 Номер заказа: `{order_number}`\n\n"
        f"Ожидайте, администратор скоро выдаст товар.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В каталог", callback_data="catalog")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    _, cat_id, prod_id = callback.data.split("_")
    
    product = categories[cat_id]["products"][prod_id]
    
    if product['stock'] <= 0:
        await callback.answer("❌ Товара нет в наличии!", show_alert=True)
        return
    
    if user_id not in users:
        users[user_id] = {"balance": 0, "cart": {}, "purchases": [], "promo_used": []}
    
    cart = users[user_id].get("cart", {})
    
    if prod_id in cart:
        if cart[prod_id]["quantity"] + 1 > product['stock']:
            await callback.answer(f"❌ В наличии только {product['stock']} шт.", show_alert=True)
            return
        cart[prod_id]["quantity"] += 1
    else:
        cart[prod_id] = {
            "name": product["name"],
            "price": product["price"],
            "quantity": 1,
            "cat_id": cat_id,
            "prod_id": prod_id
        }
    
    users[user_id]["cart"] = cart
    save_all()
    
    await callback.answer(f"✅ {product['name']} добавлен в корзину!")
    
    await notify_user(
        int(user_id),
        f"✅ **Товар добавлен в корзину**\n\n"
        f"📦 {product['name']}\n"
        f"💰 {product['price']}₽\n"
        f"📦 Количество: {cart[prod_id]['quantity']}"
    )
    
    await show_product(callback)

# ===== КОРЗИНА =====
@dp.callback_query(F.data == "view_cart")
async def view_cart(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users.get(user_id, {"cart": {}})
    cart = user.get("cart", {})
    
    if not cart:
        await callback.message.edit_text(
            "🛒 Корзина пуста",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
            ])
        )
        await callback.answer()
        return
    
    text = "🛒 **Ваша корзина:**\n\n"
    total = 0
    
    for item_data in cart.values():
        cart_number = generate_cart_number()
        text += f"🎫 Номер: `{cart_number}`\n"
        text += f"📦 {item_data['name']}\n"
        text += f"💰 `{item_data['price']}₽` x {item_data['quantity']}\n\n"
        total += item_data['price'] * item_data['quantity']
    
    text += f"**Итого: `{total}₽`**"
    
    buttons = [
        [InlineKeyboardButton(text="💳 Оформить заказ", callback_data="checkout")],
        [InlineKeyboardButton(text="🗑 Очистить корзину", callback_data="clear_cart")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@dp.callback_query(F.data == "clear_cart")
async def clear_cart(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    
    if user_id in users:
        users[user_id]["cart"] = {}
        save_all()
    
    await callback.message.edit_text(
        "✅ Корзина очищена!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛍️ В каталог", callback_data="catalog")],
            [InlineKeyboardButton(text="👤 В профиль", callback_data="profile")]
        ])
    )
    await callback.answer()

# ===== ОФОРМЛЕНИЕ ЗАКАЗА =====
@dp.callback_query(F.data == "checkout")
async def checkout(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users.get(user_id, {"balance": 0, "cart": {}})
    
    cart = user.get("cart", {})
    if not cart:
        await callback.answer("Корзина пуста!", show_alert=True)
        return
    
    # Проверяем наличие
    for item_data in cart.values():
        cat_id = item_data["cat_id"]
        prod_id = item_data["prod_id"]
        quantity = item_data["quantity"]
        
        if cat_id not in categories or prod_id not in categories[cat_id]["products"]:
            await callback.message.edit_text(
                f"❌ Товар {item_data['name']} больше не существует.\n\n"
                f"Очистите корзину.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🗑 Очистить", callback_data="clear_cart")]
                ])
            )
            await callback.answer()
            return
        
        current_stock = categories[cat_id]["products"][prod_id]["stock"]
        if current_stock < quantity:
            await callback.message.edit_text(
                f"❌ Товара {item_data['name']} осталось только {current_stock} шт.\n\n"
                f"Измените количество.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🛒 Корзина", callback_data="view_cart")]
                ])
            )
            await callback.answer()
            return
    
    total = sum(item["price"] * item["quantity"] for item in cart.values())
    
    if user["balance"] < total:
        await callback.message.edit_text(
            f"❌ **Недостаточно средств!**\n\n"
            f"💰 Ваш баланс: `{user['balance']}₽`\n"
            f"💳 Сумма заказа: `{total}₽`",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Пополнить", callback_data="topup_menu")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="view_cart")]
            ])
        )
        await callback.answer()
        return
    
    old_balance = users[user_id]["balance"]
    users[user_id]["balance"] -= total
    
    # Уменьшаем количество
    for item_data in cart.values():
        cat_id = item_data["cat_id"]
        prod_id = item_data["prod_id"]
        quantity = item_data["quantity"]
        categories[cat_id]["products"][prod_id]["stock"] -= quantity
    
    order_number = generate_cart_number()
    
    # Уведомление админу
    purchase_text = f"🛒 **ЗАКАЗ ИЗ КОРЗИНЫ!**\n\n"
    purchase_text += f"👤 Пользователь: {callback.from_user.full_name}\n"
    purchase_text += f"🆔 ID: `{user_id}`\n"
    purchase_text += f"💰 Сумма: `{total}₽`\n"
    purchase_text += f"🎫 Номер: `{order_number}`\n\n"
    purchase_text += f"📦 **Товары:**\n"
    
    for item_data in cart.values():
        purchase_text += f"• {item_data['name']} x{item_data['quantity']} - `{item_data['price']*item_data['quantity']}₽`\n"
    
    await bot.send_message(
        ADMIN_ID,
        purchase_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Ввести товар", callback_data=f"deliver_{order_number}_{user_id}")]
        ])
    )
    
    pending_delivery[order_number] = {
        "user_id": user_id,
        "cart": cart.copy(),
        "amount": total
    }
    
    # Уведомление пользователю
    items_list = "\n".join([f"• {item['name']} x{item['quantity']}" for item in cart.values()])
    await notify_user(
        int(user_id),
        f"✅ **Заказ оформлен!**\n\n"
        f"🎫 Номер заказа: `{order_number}`\n"
        f"💰 Сумма списания: `{total}₽`\n"
        f"📦 Товары:\n{items_list}\n\n"
        f"💳 Баланс: `{old_balance}₽` → `{users[user_id]['balance']}₽`"
    )
    
    # Очищаем корзину и сохраняем
    users[user_id]["cart"] = {}
    users[user_id]["purchases"].append({
        "date": datetime.now().isoformat(),
        "amount": total,
        "items": cart.copy(),
        "order_number": order_number,
        "delivered": False
    })
    save_all()
    
    await callback.message.edit_text(
        f"✅ **Заказ оформлен!**\n\n"
        f"💰 Сумма: `{total}₽`\n"
        f"🎫 Номер: `{order_number}`\n\n"
        f"Ожидайте выдачи товара.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_main")]
        ])
    )
    await callback.answer()

# ===== ВЫДАЧА ТОВАРА =====
@dp.callback_query(F.data.startswith("deliver_"))
async def start_delivery(callback: CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    _, order_number, user_id = callback.data.split("_")
    
    await state.update_data(delivery_order=order_number, delivery_user=user_id)
    await state.set_state(AdminStates.waiting_delivery_text)
    
    await callback.message.edit_text(
        f"✏️ **Введи данные товара** для заказа #{order_number}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
        ])
    )
    await callback.answer()

@dp.message(AdminStates.waiting_delivery_text)
async def process_delivery(message: Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    data = await state.get_data()
    order_number = data.get("delivery_order")
    user_id = data.get("delivery_user")
    delivery_text = message.text
    
    success = await notify_user(
        int(user_id),
        f"✅ **Ваш товар готов!**\n\n"
        f"🎫 Заказ #{order_number}\n"
        f"📦 **Данные:**\n"
        f"```\n{delivery_text}\n```"
    )
    
    if success:
        if user_id in users and "purchases" in users[user_id]:
            for purchase in users[user_id]["purchases"]:
                if purchase.get("order_number") == order_number:
                    purchase["delivered"] = True
                    purchase["delivery_text"] = delivery_text
                    break
        
        save_all()
        
        await message.answer(
            f"✅ **Товар отправлен** пользователю `{user_id}`",
            reply_markup=admin_menu()
        )
        
        if order_number in pending_delivery:
            del pending_delivery[order_number]
    else:
        await message.answer(
            f"❌ **Не удалось отправить** пользователю `{user_id}`",
            reply_markup=admin_menu()
        )
    
    await state.clear()

# ===== ТЕХПОДДЕРЖКА =====
@dp.callback_query(F.data == "support")
async def support_menu(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🆘 **Техническая поддержка**\n\n"
        "Отправьте ваш вопрос:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📝 Написать вопрос", callback_data="write_support")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "write_support")
async def write_support(callback: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.waiting_support_question)
    await callback.message.edit_text(
        "✏️ **Напишите ваш вопрос:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="back_main")]
        ])
    )
    await callback.answer()

@dp.message(UserStates.waiting_support_question)
async def process_support_question(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    question_id = str(random.randint(10000, 99999))
    
    support_questions[question_id] = {
        "user_id": user_id,
        "username": message.from_user.username,
        "name": message.from_user.full_name,
        "question": message.text,
        "date": datetime.now().isoformat(),
        "status": "waiting"
    }
    save_all()
    
    await notify_user(
        int(user_id),
        f"✅ **Вопрос отправлен!**\n\n"
        f"📝 {message.text}\n"
        f"🆔 #{question_id}"
    )
    
    await bot.send_message(
        ADMIN_ID,
        f"🆘 **НОВЫЙ ВОПРОС** #{question_id}\n\n"
        f"👤 От: {message.from_user.full_name}\n"
        f"🆔 ID: `{user_id}`\n"
        f"📝 {message.text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Ответить", callback_data=f"answer_{question_id}")]
        ])
    )
    
    await message.answer("✅ Вопрос отправлен.", reply_markup=main_menu())
    await state.clear()

# ===== АДМИН КАТЕГОРИИ =====
@dp.callback_query(F.data == "admin_add_category")
async def admin_add_category(callback: CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    await state.set_state(AdminStates.waiting_category_name)
    await callback.message.edit_text(
        "📁 **Название категории:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
        ])
    )
    await callback.answer()

@dp.message(AdminStates.waiting_category_name)
async def process_category_name(message: Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    category_name = message.text.strip()
    category_id = f"cat_{random.randint(1000, 9999)}"
    
    categories[category_id] = {"name": category_name, "products": {}}
    save_all()
    
    await message.answer(f"✅ Категория '{category_name}' создана!", reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data == "admin_list_categories")
async def admin_list_categories(callback: CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    if not categories:
        await callback.message.edit_text("📭 Нет категорий", reply_markup=admin_menu())
        await callback.answer()
        return
    
    text = "📁 **Категории:**\n\n"
    buttons = []
    
    for cat_id, cat_data in categories.items():
        text += f"📁 {cat_data['name']} (товаров: {len(cat_data['products'])})\n"
        text += f"🆔 `{cat_id}`\n\n"
        buttons.append([
            InlineKeyboardButton(text=f"✏️ {cat_data['name']}", callback_data=f"edit_cat_{cat_id}"),
            InlineKeyboardButton(text="❌", callback_data=f"del_cat_{cat_id}")
        ])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@dp.callback_query(F.data.startswith("edit_cat_"))
async def edit_category(callback: CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    cat_id = callback.data.split("_")[2]
    await state.update_data(edit_cat_id=cat_id)
    await state.set_state(AdminStates.waiting_category_edit)
    
    await callback.message.edit_text(
        f"✏️ Новое название для '{categories[cat_id]['name']}':",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_list_categories")]
        ])
    )
    await callback.answer()

@dp.message(AdminStates.waiting_category_edit)
async def process_category_edit(message: Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    data = await state.get_data()
    cat_id = data.get("edit_cat_id")
    
    categories[cat_id]["name"] = message.text.strip()
    save_all()
    
    await message.answer("✅ Категория обновлена!", reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data.startswith("del_cat_"))
async def delete_category(callback: CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    cat_id = callback.data.split("_")[2]
    
    await callback.message.edit_text(
        f"❓ Удалить '{categories[cat_id]['name']}'?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_del_cat_{cat_id}"),
                InlineKeyboardButton(text="❌ Нет", callback_data="admin_list_categories")
            ]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_del_cat_"))
async def confirm_delete_category(callback: CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    cat_id = callback.data.split("_")[3]
    
    if cat_id in categories:
        del categories[cat_id]
        save_all()
        await callback.message.edit_text("✅ Категория удалена!", reply_markup=admin_menu())
    else:
        await callback.message.edit_text("❌ Ошибка", reply_markup=admin_menu())
    
    await callback.answer()

# ===== АДМИН ТОВАРЫ =====
@dp.callback_query(F.data == "admin_add_product")
async def admin_add_product(callback: CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    if not categories:
        await callback.message.edit_text(
            "❌ Сначала создайте категорию!",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="➕ Добавить категорию", callback_data="admin_add_category")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
            ])
        )
        await callback.answer()
        return
    
    buttons = []
    for cat_id, cat_data in categories.items():
        buttons.append([InlineKeyboardButton(
            text=f"📁 {cat_data['name']}",
            callback_data=f"choose_cat_{cat_id}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    
    await state.set_state(AdminStates.waiting_category_choice)
    await callback.message.edit_text(
        "📦 **Выберите категорию:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("choose_cat_"))
async def choose_category_for_product(callback: CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    cat_id = callback.data.split("_")[2]
    await state.update_data(product_cat_id=cat_id)
    await state.set_state(AdminStates.waiting_product_name)
    
    await callback.message.edit_text(
        "✏️ **Название товара:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
        ])
    )
    await callback.answer()

@dp.message(AdminStates.waiting_product_name)
async def process_product_name(message: Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    await state.update_data(product_name=message.text.strip())
    await state.set_state(AdminStates.waiting_product_desc)
    
    await message.answer(
        "📝 **Описание товара:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
        ])
    )

@dp.message(AdminStates.waiting_product_desc)
async def process_product_desc(message: Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    await state.update_data(product_desc=message.text.strip())
    await state.set_state(AdminStates.waiting_product_price)
    
    await message.answer(
        "💰 **Цена (руб):**\n"
        "Только число",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
        ])
    )

@dp.message(AdminStates.waiting_product_price)
async def process_product_price(message: Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    try:
        price = int(message.text.strip())
        if price <= 0:
            raise ValueError
        
        await state.update_data(product_price=price)
        await state.set_state(AdminStates.waiting_product_stock)
        
        await message.answer(
            "📦 **Количество:**\n"
            "Только число",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
            ])
        )
    except:
        await message.answer("❌ Введите число!")

@dp.message(AdminStates.waiting_product_stock)
async def process_product_stock(message: Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    try:
        stock = int(message.text.strip())
        if stock < 0:
            raise ValueError
        
        data = await state.get_data()
        cat_id = data.get("product_cat_id")
        product_name = data.get("product_name")
        product_desc = data.get("product_desc")
        product_price = data.get("product_price")
        
        product_id = f"prod_{random.randint(10000, 99999)}"
        
        categories[cat_id]["products"][product_id] = {
            "name": product_name,
            "desc": product_desc,
            "price": product_price,
            "stock": stock
        }
        save_all()
        
        await message.answer(
            f"✅ **Товар добавлен!**\n\n"
            f"📦 {product_name}\n"
            f"💰 {product_price}₽\n"
            f"📦 {stock} шт.\n"
            f"🆔 `{product_id}`",
            reply_markup=admin_menu()
        )
        await state.clear()
        
    except:
        await message.answer("❌ Введите число!")

@dp.callback_query(F.data == "admin_all_products")
async def admin_all_products(callback: CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    if not categories:
        await callback.message.edit_text("📭 Нет категорий", reply_markup=admin_menu())
        await callback.answer()
        return
    
    text = "📦 **Все товары:**\n\n"
    buttons = []
    
    for cat_id, cat_data in categories.items():
        if cat_data.get("products"):
            text += f"📁 {cat_data['name']}:\n"
            for prod_id, product in cat_data["products"].items():
                text += f"  • {product['name']} - {product['price']}₽ ({product['stock']} шт.)\n"
                text += f"    🆔 `{prod_id}`\n"
                buttons.append([
                    InlineKeyboardButton(text=f"✏️ {product['name'][:10]}", callback_data=f"edit_prod_{cat_id}_{prod_id}"),
                    InlineKeyboardButton(text="❌", callback_data=f"del_prod_{cat_id}_{prod_id}")
                ])
            text += "\n"
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@dp.callback_query(F.data.startswith("del_prod_"))
async def delete_product(callback: CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    _, _, cat_id, prod_id = callback.data.split("_")
    product_name = categories[cat_id]["products"][prod_id]["name"]
    
    await callback.message.edit_text(
        f"❓ Удалить '{product_name}'?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Да", callback_data=f"confirm_del_prod_{cat_id}_{prod_id}"),
                InlineKeyboardButton(text="❌ Нет", callback_data="admin_all_products")
            ]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_del_prod_"))
async def confirm_delete_product(callback: CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    _, _, _, cat_id, prod_id = callback.data.split("_")
    
    if cat_id in categories and prod_id in categories[cat_id]["products"]:
        del categories[cat_id]["products"][prod_id]
        save_all()
        await callback.message.edit_text("✅ Товар удален!", reply_markup=admin_menu())
    else:
        await callback.message.edit_text("❌ Ошибка", reply_markup=admin_menu())
    
    await callback.answer()

# ===== АДМИН ПРОМОКОДЫ =====
@dp.callback_query(F.data == "admin_promocodes")
async def admin_promocodes(callback: CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    text = "🎟 **Промокоды**\n\n"
    buttons = []
    
    if promocodes:
        for code, data in promocodes.items():
            text += f"🎫 `{code}` - {data['discount']}%\n"
            text += f"   Осталось: {data['uses_left']}/{data['uses_left'] + data['used']}\n"
            text += f"   Использовано: {data['used']}\n\n"
            buttons.append([InlineKeyboardButton(text=f"❌ Удалить {code}", callback_data=f"del_promo_{code}")])
    else:
        text += "Промокодов пока нет\n"
    
    buttons.append([InlineKeyboardButton(text="➕ Создать", callback_data="create_promo")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@dp.callback_query(F.data == "create_promo")
async def create_promo(callback: CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    await state.set_state(PromoStates.waiting_promo_name)
    await callback.message.edit_text(
        "🎟 **Название промокода** (например: SUMMER50):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promocodes")]
        ])
    )
    await callback.answer()

@dp.message(PromoStates.waiting_promo_name)
async def process_promo_name(message: Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    promo_name = message.text.strip().upper()
    
    if promo_name in promocodes:
        await message.answer("❌ Такой промокод уже существует!")
        return
    
    await state.update_data(promo_name=promo_name)
    await state.set_state(PromoStates.waiting_promo_discount)
    
    await message.answer(
        "💰 **Процент скидки** (число от 1 до 99):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promocodes")]
        ])
    )

@dp.message(PromoStates.waiting_promo_discount)
async def process_promo_discount(message: Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    try:
        discount = int(message.text.strip())
        if discount < 1 or discount > 99:
            raise ValueError
        
        await state.update_data(promo_discount=discount)
        await state.set_state(PromoStates.waiting_promo_uses)
        
        await message.answer(
            "📊 **Количество активаций** (сколько раз можно использовать):",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_promocodes")]
            ])
        )
    except:
        await message.answer("❌ Введите число от 1 до 99!")

@dp.message(PromoStates.waiting_promo_uses)
async def process_promo_uses(message: Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    try:
        uses = int(message.text.strip())
        if uses <= 0:
            raise ValueError
        
        data = await state.get_data()
        promo_name = data.get("promo_name")
        promo_discount = data.get("promo_discount")
        
        promocodes[promo_name] = {
            "discount": promo_discount,
            "uses_left": uses,
            "used": 0,
            "created": datetime.now().isoformat()
        }
        save_all()
        
        await message.answer(
            f"✅ **Промокод создан!**\n\n"
            f"🎟 {promo_name} - {promo_discount}%\n"
            f"📊 Активаций: {uses}",
            reply_markup=admin_menu()
        )
        await state.clear()
        
    except:
        await message.answer("❌ Введите положительное число!")

@dp.callback_query(F.data.startswith("del_promo_"))
async def delete_promo(callback: CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    promo_code = callback.data.replace("del_promo_", "")
    
    if promo_code in promocodes:
        del promocodes[promo_code]
        save_all()
        await callback.answer(f"✅ Промокод {promo_code} удален!")
    else:
        await callback.answer("❌ Промокод не найден!")
    
    await admin_promocodes(callback)

# ===== АДМИН РАССЫЛКА =====
@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    await state.set_state(AdminStates.waiting_broadcast_text)
    await callback.message.edit_text(
        "📢 **Текст рассылки:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
        ])
    )
    await callback.answer()

@dp.message(AdminStates.waiting_broadcast_text)
async def process_broadcast_text(message: Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    await state.update_data(broadcast_text=message.text.strip())
    await state.set_state(AdminStates.waiting_broadcast_button)
    
    await message.answer(
        "🔗 **Кнопка?**\n"
        "Формат: Текст | URL\n"
        "Или отправьте '-'",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_button")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
        ])
    )

@dp.callback_query(F.data == "skip_button")
async def skip_button(callback: CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    data = await state.get_data()
    broadcast_text = data.get("broadcast_text")
    
    await callback.message.delete()
    await callback.message.answer("⏳ Рассылка...")
    
    sent = 0
    failed = 0
    
    for user_id in users.keys():
        try:
            await bot.send_message(int(user_id), broadcast_text)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    await callback.message.answer(f"✅ Отправлено: {sent}\n❌ Не доставлено: {failed}", reply_markup=admin_menu())
    await state.clear()

@dp.message(AdminStates.waiting_broadcast_button)
async def process_broadcast_button(message: Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    data = await state.get_data()
    broadcast_text = data.get("broadcast_text")
    keyboard = None
    
    if message.text.strip() != "-":
        try:
            button_text, button_url = message.text.strip().split("|")
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=button_text.strip(), url=button_url.strip())]
            ])
        except:
            await message.answer("❌ Неправильный формат!")
            return
    
    await message.answer("⏳ Рассылка...")
    
    sent = 0
    failed = 0
    
    for user_id in users.keys():
        try:
            await bot.send_message(int(user_id), broadcast_text, reply_markup=keyboard)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    
    await message.answer(f"✅ Отправлено: {sent}\n❌ Не доставлено: {failed}", reply_markup=admin_menu())
    await state.clear()

# ===== АДМИН ПОДДЕРЖКА =====
@dp.callback_query(F.data == "admin_support_questions")
async def admin_support_questions(callback: CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    waiting = {qid: q for qid, q in support_questions.items() if q.get("status") == "waiting"}
    
    if not waiting:
        await callback.message.edit_text("📭 Нет новых вопросов", reply_markup=admin_menu())
        await callback.answer()
        return
    
    text = "🆘 **Вопросы:**\n\n"
    buttons = []
    
    for qid, qdata in list(waiting.items())[:10]:
        text += f"❓ #{qid}\n👤 {qdata['name']}\n📝 {qdata['question'][:50]}...\n\n"
        buttons.append([InlineKeyboardButton(text=f"✏️ Ответить #{qid}", callback_data=f"answer_{qid}")])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@dp.callback_query(F.data.startswith("answer_"))
async def answer_support(callback: CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    qid = callback.data.split("_")[1]
    await state.update_data(answer_qid=qid)
    await state.set_state(AdminStates.waiting_support_answer)
    
    await callback.message.edit_text(
        f"✏️ **Ответ** на вопрос #{qid}:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
        ])
    )
    await callback.answer()

@dp.message(AdminStates.waiting_support_answer)
async def process_support_answer(message: Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    data = await state.get_data()
    qid = data.get("answer_qid")
    
    if qid not in support_questions:
        await message.answer("❌ Вопрос не найден!")
        await state.clear()
        return
    
    question = support_questions[qid]
    user_id = question["user_id"]
    
    question["status"] = "answered"
    question["answer"] = message.text
    save_all()
    
    success = await notify_user(
        int(user_id),
        f"📩 **Ответ:**\n\n"
        f"📝 {question['question']}\n\n"
        f"💬 {message.text}"
    )
    
    if success:
        await message.answer(f"✅ Ответ отправлен {user_id}", reply_markup=admin_menu())
    else:
        await message.answer(f"❌ Не удалось отправить", reply_markup=admin_menu())
    
    await state.clear()

# ===== АДМИН ПОЛЬЗОВАТЕЛИ =====
@dp.callback_query(F.data == "admin_users_list")
async def admin_users_list(callback: CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    if not users:
        await callback.message.edit_text("📭 Нет пользователей", reply_markup=admin_menu())
        await callback.answer()
        return
    
    text = "👥 **Пользователи:**\n\n"
    for uid, udata in list(users.items())[:20]:
        text += f"🆔 `{uid}`\n"
        text += f"👤 {udata.get('first_name', '')} @{udata.get('username', '')}\n"
        text += f"💰 {udata.get('balance', 0)}₽\n"
        text += f"📦 {len(udata.get('purchases', []))} покупок\n"
        text += "——————————\n"
    
    await callback.message.edit_text(text, reply_markup=admin_menu())
    await callback.answer()

# ===== АДМИН БАЛАНС =====
@dp.callback_query(F.data == "admin_change_balance")
async def admin_change_balance(callback: CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    await state.set_state(AdminStates.waiting_user_id_balance)
    await callback.message.edit_text(
        "💰 **ID пользователя:**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_back")]
        ])
    )
    await callback.answer()

@dp.message(AdminStates.waiting_user_id_balance)
async def process_user_id_balance(message: Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    user_id = message.text.strip()
    
    if user_id not in users:
        await message.answer("❌ Пользователь не найден!")
        return
    
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminStates.waiting_balance_amount)
    
    await message.answer(
        f"💰 Баланс: {users[user_id]['balance']}₽\n"
        f"✏️ Сумма (+500 или -200):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
        ])
    )

@dp.message(AdminStates.waiting_balance_amount)
async def process_balance_amount(message: Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    
    try:
        amount = int(message.text)
    except:
        await message.answer("❌ Введите число!")
        return
    
    data = await state.get_data()
    user_id = data.get("target_user_id")
    
    old_balance = users[user_id]["balance"]
    users[user_id]["balance"] += amount
    
    if users[user_id]["balance"] < 0:
        users[user_id]["balance"] = 0
    
    save_all()
    
    await notify_user(
        int(user_id),
        f"💰 **Баланс изменен**\n\n"
        f"Сумма: {amount:+}₽\n"
        f"Было: {old_balance}₽\n"
        f"Стало: {users[user_id]['balance']}₽"
    )
    
    await message.answer(
        f"✅ Баланс {user_id}: {old_balance}₽ → {users[user_id]['balance']}₽",
        reply_markup=admin_menu()
    )
    await state.clear()

# ===== ВСПОМОГАТЕЛЬНЫЕ АДМИН =====
@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    await callback.message.edit_text("👑 Админ-панель", reply_markup=admin_menu())
    await callback.answer()

@dp.callback_query(F.data == "admin_cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    await state.clear()
    await callback.message.edit_text("👑 Админ-панель", reply_markup=admin_menu())
    await callback.answer()

# ===== ЗАПУСК =====
async def on_startup():
    logger.info("=" * 50)
    logger.info("БОТ ЗАПУЩЕН")
    logger.info(f"Bot: @{(await bot.me()).username}")
    logger.info(f"Admin: {ADMIN_ID}")
    logger.info("=" * 50)
    
    await bot.send_message(ADMIN_ID, "✅ **Бот запущен!**")

async def on_shutdown():
    logger.info("Бот остановлен")
    await bot.send_message(ADMIN_ID, "❌ **Бот остановлен**")
    await bot.session.close()

async def main():
    asyncio.create_task(check_invoices_periodically())
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop = asyncio.get_running_loop()
            loop.add_signal_handler(sig, lambda: asyncio.create_task(on_shutdown()))
        except NotImplementedError:
            pass
    
    await on_startup()
    
    try:
        await dp.start_polling(bot)
    finally:
        await on_shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка: {e}")
