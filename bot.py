#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Shop Bot - ПОЛНАЯ ВЕРСИЯ СО ВСЕМИ ЗАВИСИМОСТЯМИ
Все библиотеки уже подключены, ничего устанавливать не нужно!
"""

# ========== ВСТРОЕННЫЕ БИБЛИОТЕКИ (уже есть в Python) ==========
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

# ========== УСТАНОВЛЕННЫЕ БИБЛИОТЕКИ (уже есть) ==========
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

# ========== ТВОИ ДАННЫЕ (УЖЕ ВСТАВЛЕНЫ) ==========
BOT_TOKEN = "8674038652:AAHPnGq-hteuyBDRNI6F-5Ea1NQm8wE31ZI"
ADMIN_ID = 8402407852
CRYPTOBOT_TOKEN = "545243:AAbNak8pGgjhloWOz2SfoiUcLBfAijfhc6Q"
SUPPORT_USERNAME = "@alooopaq"
# ================================================

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
    waiting_category_name = State()
    waiting_category_edit = State()
    waiting_category_choice = State()
    waiting_product_name = State()
    waiting_product_desc = State()
    waiting_product_stock = State()
    waiting_product_price = State()
    waiting_product_edit = State()
    waiting_broadcast_text = State()
    waiting_broadcast_button = State()
    waiting_support_reply = State()
    waiting_support_answer = State()
    waiting_user_id_balance = State()
    waiting_balance_amount = State()
    waiting_delivery_text = State()

class UserStates(StatesGroup):
    waiting_support_question = State()
    waiting_crypto_amount = State()

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
pending_delivery = {}

def save_all():
    save_data("users", users)
    save_data("categories", categories)
    save_data("support_questions", support_questions)
    save_data("crypto_invoices", crypto_invoices)

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

# ===== ХЕНДЛЕРЫ =====
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user_id = str(message.from_user.id)
    
    if user_id not in users:
        users[user_id] = {
            "balance": 0,
            "cart": {},
            "purchases": [],
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
    text += f"RAM: `{memory.percent}%`\n"
    text += f"Аптайм: бот работает"
    
    await message.answer(text)

@dp.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "👋 Здравствуй, этот маркет для тебя, тут ты можешь приобрести много чего)\n\n"
        "👇 ЖМИ КАТАЛОГ 👇",
        reply_markup=main_menu()
    )
    await callback.answer()

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
        buttons.append([InlineKeyboardButton(
            text=f"{product['name']} - {product['price']}₽",
            callback_data=f"product_{cat_id}_{prod_id}"
        )])
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
    
    text = f"📦 **{product['name']}**\n\n"
    text += f"📝 {product['desc']}\n\n"
    text += f"💰 Цена: `{product['price']}₽`\n"
    text += f"📦 В наличии: `{product['stock']} шт.`\n\n"
    text += f"🆔 Номер товара: `{prod_id}`"
    
    buttons = [
        [InlineKeyboardButton(text="➕ Добавить в корзину", callback_data=f"add_{cat_id}_{prod_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"category_{cat_id}")]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    _, cat_id, prod_id = callback.data.split("_")
    
    product = categories[cat_id]["products"][prod_id]
    
    if user_id not in users:
        users[user_id] = {"balance": 0, "cart": {}, "purchases": []}
    
    cart = users[user_id].get("cart", {})
    
    if prod_id in cart:
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
        [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
    ]
    
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await callback.answer()

@dp.callback_query(F.data == "checkout")
async def checkout(callback: CallbackQuery):
    user_id = str(callback.from_user.id)
    user = users.get(user_id, {"balance": 0, "cart": {}})
    
    cart = user.get("cart", {})
    if not cart:
        await callback.answer("Корзина пуста!", show_alert=True)
        return
    
    total = sum(item["price"] * item["quantity"] for item in cart.values())
    
    if user["balance"] < total:
        await callback.message.edit_text(
            f"❌ **Недостаточно средств!**\n\n"
            f"💰 Ваш баланс: `{user['balance']}₽`\n"
            f"💳 Сумма заказа: `{total}₽`\n\n"
            f"Пополните баланс в профиле.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="💰 Пополнить", callback_data="topup_menu")],
                [InlineKeyboardButton(text="🔙 Назад", callback_data="view_cart")]
            ])
        )
        await callback.answer()
        return
    
    old_balance = users[user_id]["balance"]
    users[user_id]["balance"] -= total
    new_balance = users[user_id]["balance"]
    
    order_number = generate_cart_number()
    
    purchase_text = f"🛒 **НОВАЯ ПОКУПКА!**\n\n"
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
    
    items_list = "\n".join([f"• {item['name']} x{item['quantity']}" for item in cart.values()])
    await notify_user(
        int(user_id),
        f"✅ **Заказ оформлен!**\n\n"
        f"🎫 Номер заказа: `{order_number}`\n"
        f"💰 Сумма списания: `{total}₽`\n"
        f"📦 Товары:\n{items_list}\n\n"
        f"💳 Баланс: `{old_balance}₽` → `{new_balance}₽`\n\n"
        f"⏳ Ожидайте, администратор скоро выдаст товар."
    )
    
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
        f"💰 С баланса списано: `{total}₽`\n"
        f"🎫 Номер заказа: `{order_number}`\n\n"
        f"Ожидайте, администратор скоро выдаст товар.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_main")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("deliver_"))
async def start_delivery(callback: CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Это не для тебя!")
        return
    
    _, order_number, user_id = callback.data.split("_")
    
    await state.update_data(delivery_order=order_number, delivery_user=user_id)
    await state.set_state(AdminStates.waiting_delivery_text)
    
    await callback.message.edit_text(
        f"✏️ **Введи текст/данные товара** для заказа #{order_number}",
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
        f"```\n{delivery_text}\n```\n\n"
        f"⬇️ Скопируйте данные выше и используйте по назначению."
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
            f"❌ **Не удалось отправить товар** пользователю `{user_id}`\n"
            f"Возможно, пользователь заблокировал бота.",
            reply_markup=admin_menu()
        )
    
    await state.clear()

@dp.callback_query(F.data == "support")
async def support_menu(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🆘 **Техническая поддержка**\n\n"
        "Отправьте ваш вопрос, желательно укажите номер товара "
        "или кратко опишите вопрос.",
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
        f"✅ **Ваш вопрос отправлен!**\n\n"
        f"📝 Вопрос: {message.text}\n"
        f"🆔 Номер: #{question_id}\n\n"
        f"⏳ Ожидайте ответа от поддержки."
    )
    
    await bot.send_message(
        ADMIN_ID,
        f"🆘 **НОВЫЙ ВОПРОС** #{question_id}\n\n"
        f"👤 От: {message.from_user.full_name} (@{message.from_user.username})\n"
        f"🆔 ID: `{user_id}`\n"
        f"📝 Вопрос: {message.text}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Ответить", callback_data=f"answer_{question_id}")]
        ])
    )
    
    await message.answer(
        "✅ Ваш вопрос отправлен администратору. Ожидайте ответа.",
        reply_markup=main_menu()
    )
    await state.clear()

@dp.callback_query(F.data.startswith("answer_"))
async def answer_support(callback: CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Не для тебя!")
        return
    
    qid = callback.data.split("_")[1]
    await state.update_data(answer_qid=qid)
    await state.set_state(AdminStates.waiting_support_answer)
    
    await callback.message.edit_text(
        f"✏️ **Введи ответ** на вопрос #{qid}:",
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
    question["answer_date"] = datetime.now().isoformat()
    save_all()
    
    success = await notify_user(
        int(user_id),
        f"📩 **Ответ от поддержки**\n\n"
        f"📝 Ваш вопрос: {question['question']}\n\n"
        f"💬 Ответ: {message.text}"
    )
    
    if success:
        await message.answer(
            f"✅ Ответ отправлен пользователю `{user_id}`",
            reply_markup=admin_menu()
        )
    else:
        await message.answer(
            f"❌ Не удалось отправить пользователю `{user_id}`",
            reply_markup=admin_menu()
        )
    
    await state.clear()

@dp.callback_query(F.data == "admin_users_list")
async def admin_users_list(callback: CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Не для тебя!")
        return
    
    if not users:
        await callback.message.edit_text(
            "📭 Нет пользователей",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
            ])
        )
        await callback.answer()
        return
    
    text = "👥 **ВСЕ ПОЛЬЗОВАТЕЛИ:**\n\n"
    for uid, udata in list(users.items())[:20]:
        text += f"🆔 `{uid}`\n"
        text += f"👤 {udata.get('first_name', '')} @{udata.get('username', '')}\n"
        text += f"💰 {udata.get('balance', 0)}₽\n"
        text += f"📦 {len(udata.get('purchases', []))} покупок\n"
        text += "——————————\n"
    
    if len(users) > 20:
        text += f"\n... и еще {len(users)-20} пользователей"
    
    await callback.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")]
        ])
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_change_balance")
async def admin_change_balance(callback: CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Не для тебя!")
        return
    
    await state.set_state(AdminStates.waiting_user_id_balance)
    await callback.message.edit_text(
        "💰 **Изменение баланса**\n\n"
        "Введи ID пользователя:",
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
        await message.answer(
            "❌ Пользователь не найден!\n\n"
            "Введи ID пользователя еще раз:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
            ])
        )
        return
    
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminStates.waiting_balance_amount)
    
    await message.answer(
        f"💰 Текущий баланс пользователя {user_id}: `{users[user_id]['balance']}₽`\n\n"
        f"Введи сумму изменения (например: +500 или -200):",
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
        await message.answer(
            "❌ Введи число!\n\n"
            "Пример: +500 или -200",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="❌ Отмена", callback_data="admin_cancel")]
            ])
        )
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
        f"💰 **Изменение баланса**\n\n"
        f"Сумма: `{amount:+}₽`\n"
        f"Было: `{old_balance}₽`\n"
        f"Стало: `{users[user_id]['balance']}₽`\n\n"
        f"👤 Администратор изменил ваш баланс."
    )
    
    await message.answer(
        f"✅ **Баланс изменен!**\n\n"
        f"🆔 Пользователь: `{user_id}`\n"
        f"💰 Было: `{old_balance}₽`\n"
        f"💰 Стало: `{users[user_id]['balance']}₽`",
        reply_markup=admin_menu()
    )
    
    await state.clear()

@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Не для тебя!")
        return
    
    await callback.message.edit_text(
        "👑 **Админ-панель**\n\n"
        "Выберите действие:",
        reply_markup=admin_menu()
    )
    await callback.answer()

@dp.callback_query(F.data == "admin_cancel")
async def admin_cancel(callback: CallbackQuery, state: FSMContext):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Не для тебя!")
        return
    
    await state.clear()
    await callback.message.edit_text(
        "👑 **Админ-панель**\n\n"
        "Выберите действие:",
        reply_markup=admin_menu()
    )
    await callback.answer()

# ===== ЗАПУСК БОТА =====
async def on_startup():
    logger.info("=" * 50)
    logger.info("БОТ ЗАПУСКАЕТСЯ")
    logger.info(f"Bot ID: {(await bot.me()).id}")
    logger.info(f"Bot Username: @{(await bot.me()).username}")
    logger.info(f"Admin ID: {ADMIN_ID}")
    logger.info(f"Support: {SUPPORT_USERNAME}")
    logger.info("=" * 50)
    
    await bot.send_message(
        ADMIN_ID,
        f"✅ **Бот запущен!**\n\n"
        f"🤖 @{(await bot.me()).username}\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )

async def on_shutdown():
    logger.info("Бот останавливается...")
    await bot.send_message(
        ADMIN_ID,
        "❌ **Бот остановлен**"
    )
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
        logger.info("Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
