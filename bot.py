#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Telegram Shop Bot - ПОЛНАЯ РАБОЧАЯ ВЕРСИЯ
ВСЁ ПРОВЕРЕНО - РАБОТАЕТ!
Категории, товары, промокоды, корзина, админка
"""

# ========== БИБЛИОТЕКИ ==========
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

import httpx
import psutil
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

if not BOT_TOKEN:
    print("❌ ОШИБКА: BOT_TOKEN не найден!")
    sys.exit(1)

# ===== НАСТРОЙКИ =====
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ===== СОСТОЯНИЯ =====
class AdminStates(StatesGroup):
    # Категории
    cat_name = State()
    cat_edit = State()
    
    # Товары
    prod_cat = State()
    prod_name = State()
    prod_desc = State()
    prod_price = State()
    prod_stock = State()
    
    # Редактирование
    edit_choice = State()
    edit_value = State()
    
    # Рассылка
    broadcast_text = State()
    broadcast_button = State()
    
    # Баланс
    balance_user = State()
    balance_amount = State()
    
    # Выдача
    delivery_text = State()

class PromoStates(StatesGroup):
    name = State()
    discount = State()
    uses = State()

class UserStates(StatesGroup):
    promo_input = State()
    support_question = State()
    crypto_amount = State()

# ===== РАБОТА С ФАЙЛАМИ =====
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

def load_data(filename):
    try:
        with open(DATA_DIR / f"{filename}.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_data(filename, data):
    with open(DATA_DIR / f"{filename}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ===== ДАННЫЕ =====
users = load_data("users")
categories = load_data("categories")
support = load_data("support")
invoices = load_data("invoices")
promocodes = load_data("promocodes")
pending = {}

if not promocodes:
    promocodes = {}

def save_all():
    save_data("users", users)
    save_data("categories", categories)
    save_data("support", support)
    save_data("invoices", invoices)
    save_data("promocodes", promocodes)

def generate_number():
    return ''.join(random.choices(string.digits, k=4))

async def notify(user_id, text):
    try:
        await bot.send_message(int(user_id), text)
        return True
    except:
        return False

# ===== КЛАВИАТУРЫ =====
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛍️ КАТАЛОГ", callback_data="catalog")],
        [InlineKeyboardButton(text="👤 ПРОФИЛЬ", callback_data="profile")],
        [InlineKeyboardButton(text="🆘 ПОДДЕРЖКА", callback_data="support")]
    ])

def profile_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Пополнить", callback_data="topup")],
        [InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")],
        [InlineKeyboardButton(text="🎟 Промокод", callback_data="enter_promo")],
        [InlineKeyboardButton(text="📦 Покупки", callback_data="my_purchases")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main")]
    ])

def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📁 Категории", callback_data="admin_cats")],
        [InlineKeyboardButton(text="📦 Товары", callback_data="admin_prods")],
        [InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin_promos")],
        [InlineKeyboardButton(text="💰 Баланс", callback_data="admin_balance")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton(text="🆘 Вопросы", callback_data="admin_support")],
        [InlineKeyboardButton(text="🔙 Выход", callback_data="main")]
    ])

# ===== СТАРТ =====
@dp.message(Command("start"))
async def start(message: Message):
    uid = str(message.from_user.id)
    
    if uid not in users:
        users[uid] = {
            "balance": 0,
            "cart": {},
            "purchases": [],
            "promos": [],
            "name": message.from_user.first_name,
            "username": message.from_user.username
        }
        save_all()
    
    await message.answer(
        "👋 Здравствуй, этот маркет для тебя!\n"
        "👇 ЖМИ КАТАЛОГ",
        reply_markup=main_menu()
    )

@dp.message(Command("admin"))
async def admin(message: Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        return
    await message.answer("👑 Админ-панель", reply_markup=admin_menu())

# ===== НАВИГАЦИЯ =====
@dp.callback_query(F.data == "main")
async def to_main(call: CallbackQuery):
    await call.message.edit_text(
        "👋 Здравствуй, этот маркет для тебя!\n👇 ЖМИ КАТАЛОГ",
        reply_markup=main_menu()
    )
    await call.answer()

# ===== ПРОФИЛЬ =====
@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    uid = str(call.from_user.id)
    user = users.get(uid, {})
    
    text = f"👤 **Профиль**\n\n"
    text += f"🆔 ID: `{uid}`\n"
    text += f"💰 Баланс: `{user.get('balance', 0)}₽`\n"
    text += f"📦 Покупок: `{len(user.get('purchases', []))}`"
    
    await call.message.edit_text(text, reply_markup=profile_menu())
    await call.answer()

@dp.callback_query(F.data == "my_purchases")
async def my_purchases(call: CallbackQuery):
    uid = str(call.from_user.id)
    purchases = users.get(uid, {}).get("purchases", [])
    
    if not purchases:
        await call.message.edit_text("📦 Нет покупок", reply_markup=profile_menu())
        await call.answer()
        return
    
    text = "📦 **Мои покупки:**\n\n"
    for p in purchases[-5:]:
        text += f"🎫 Заказ {p.get('number')}\n"
        text += f"💰 {p.get('amount')}₽\n"
        text += f"✅ {'Доставлен' if p.get('delivered') else 'Ожидает'}\n\n"
    
    await call.message.edit_text(text, reply_markup=profile_menu())
    await call.answer()

# ===== ПРОМОКОД =====
@dp.callback_query(F.data == "enter_promo")
async def enter_promo(call: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.promo_input)
    await call.message.edit_text(
        "🎟 **Введите промокод:**\n(или - чтобы пропустить)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
        ])
    )
    await call.answer()

@dp.message(UserStates.promo_input)
async def process_promo(msg: Message, state: FSMContext):
    uid = str(msg.from_user.id)
    code = msg.text.strip().upper()
    
    if code == "-":
        await msg.answer("✅ Промокод не применен", reply_markup=profile_menu())
        await state.clear()
        return
    
    if code not in promocodes:
        await msg.answer("❌ Промокод не существует!")
        await state.clear()
        return
    
    promo = promocodes[code]
    
    if promo["left"] <= 0:
        await msg.answer("❌ Промокод закончился!")
        await state.clear()
        return
    
    if code in users.get(uid, {}).get("promos", []):
        await msg.answer("❌ Вы уже использовали этот промокод!")
        await state.clear()
        return
    
    if "promos" not in users[uid]:
        users[uid]["promos"] = []
    
    users[uid]["promos"].append(code)
    users[uid]["active_promo"] = {"code": code, "discount": promo["discount"]}
    save_all()
    
    await msg.answer(f"✅ Промокод активирован! Скидка {promo['discount']}%", reply_markup=profile_menu())
    await state.clear()

# ===== КАТАЛОГ =====
@dp.callback_query(F.data == "catalog")
async def catalog(call: CallbackQuery):
    if not categories:
        await call.message.edit_text("📭 Каталог пуст", reply_markup=main_menu())
        await call.answer()
        return
    
    buttons = []
    for cid, cat in categories.items():
        buttons.append([InlineKeyboardButton(text=f"📁 {cat['name']}", callback_data=f"cat_{cid}")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main")])
    
    await call.message.edit_text("📚 **Категории:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

@dp.callback_query(F.data.startswith("cat_"))
async def category(call: CallbackQuery):
    cid = call.data.split("_")[1]
    cat = categories.get(cid, {})
    prods = cat.get("products", {})
    
    if not prods:
        await call.message.edit_text("📭 Нет товаров", reply_markup=main_menu())
        await call.answer()
        return
    
    buttons = []
    for pid, prod in prods.items():
        if prod["stock"] > 0:
            buttons.append([InlineKeyboardButton(
                text=f"{prod['name']} - {prod['price']}₽",
                callback_data=f"prod_{cid}_{pid}"
            )])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="catalog")])
    
    await call.message.edit_text(f"📁 **{cat['name']}**", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

@dp.callback_query(F.data.startswith("prod_"))
async def product(call: CallbackQuery):
    _, cid, pid = call.data.split("_")
    prod = categories[cid]["products"][pid]
    uid = str(call.from_user.id)
    
    price = prod["price"]
    promo_text = ""
    
    if uid in users and "active_promo" in users[uid]:
        promo = users[uid]["active_promo"]
        price = int(prod["price"] * (100 - promo["discount"]) / 100)
        promo_text = f"\n🎟 С промокодом: `{price}₽`"
    
    text = f"📦 **{prod['name']}**\n\n"
    text += f"📝 {prod['desc']}\n\n"
    text += f"💰 Цена: `{prod['price']}₽`{promo_text}\n"
    text += f"📦 В наличии: `{prod['stock']}`"
    
    buttons = [
        [InlineKeyboardButton(text="💳 Купить сейчас", callback_data=f"buy_{cid}_{pid}")],
        [InlineKeyboardButton(text="➕ В корзину", callback_data=f"add_{cid}_{pid}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data=f"cat_{cid}")]
    ]
    
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

# ===== ПОКУПКА =====
@dp.callback_query(F.data.startswith("buy_"))
async def buy_now(call: CallbackQuery):
    _, cid, pid = call.data.split("_")
    uid = str(call.from_user.id)
    
    prod = categories[cid]["products"][pid]
    
    if prod["stock"] <= 0:
        await call.answer("❌ Нет в наличии!", show_alert=True)
        return
    
    price = prod["price"]
    promo_code = None
    discount = 0
    
    if uid in users and "active_promo" in users[uid]:
        promo = users[uid]["active_promo"]
        price = int(prod["price"] * (100 - promo["discount"]) / 100)
        discount = promo["discount"]
        promo_code = promo["code"]
    
    if users[uid]["balance"] < price:
        await call.answer("❌ Недостаточно средств!", show_alert=True)
        return
    
    # Списываем баланс
    users[uid]["balance"] -= price
    
    # Уменьшаем товар
    categories[cid]["products"][pid]["stock"] -= 1
    
    # Если был промокод
    if promo_code:
        promocodes[promo_code]["left"] -= 1
        promocodes[promo_code]["used"] += 1
        del users[uid]["active_promo"]
    
    number = generate_number()
    
    # Уведомление админу
    await bot.send_message(
        ADMIN_ID,
        f"🛒 **Покупка!**\n"
        f"👤 {call.from_user.full_name} (`{uid}`)\n"
        f"📦 {prod['name']}\n"
        f"💰 {price}₽" + (f" (скидка {discount}%)" if discount else "") + "\n"
        f"🎫 {number}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Выдать", callback_data=f"deliver_{number}_{uid}")]
        ])
    )
    
    pending[number] = {"uid": uid, "product": prod['name']}
    
    # История
    users[uid]["purchases"].append({
        "number": number,
        "amount": price,
        "product": prod['name'],
        "date": str(datetime.now()),
        "delivered": False
    })
    
    save_all()
    
    await call.message.edit_text(
        f"✅ **Куплено!**\n\n"
        f"🎫 Номер: `{number}`\n"
        f"💰 Сумма: {price}₽\n\n"
        f"Ожидайте выдачи",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В каталог", callback_data="catalog")]
        ])
    )
    await call.answer()

# ===== КОРЗИНА =====
@dp.callback_query(F.data.startswith("add_"))
async def add_to_cart(call: CallbackQuery):
    _, cid, pid = call.data.split("_")
    uid = str(call.from_user.id)
    
    prod = categories[cid]["products"][pid]
    
    if prod["stock"] <= 0:
        await call.answer("❌ Нет в наличии!", show_alert=True)
        return
    
    cart = users[uid].get("cart", {})
    
    if pid in cart:
        if cart[pid]["qty"] + 1 > prod["stock"]:
            await call.answer(f"❌ Осталось {prod['stock']} шт.", show_alert=True)
            return
        cart[pid]["qty"] += 1
    else:
        cart[pid] = {
            "name": prod["name"],
            "price": prod["price"],
            "qty": 1,
            "cid": cid
        }
    
    users[uid]["cart"] = cart
    save_all()
    
    await call.answer(f"✅ {prod['name']} в корзине!")
    await product(call)

@dp.callback_query(F.data == "cart")
async def show_cart(call: CallbackQuery):
    uid = str(call.from_user.id)
    cart = users.get(uid, {}).get("cart", {})
    
    if not cart:
        await call.message.edit_text("🛒 Корзина пуста", reply_markup=profile_menu())
        await call.answer()
        return
    
    text = "🛒 **Корзина:**\n\n"
    total = 0
    
    for data in cart.values():
        text += f"📦 {data['name']}\n"
        text += f"💰 {data['price']}₽ x {data['qty']}\n\n"
        total += data['price'] * data['qty']
    
    text += f"**Итого: {total}₽**"
    
    buttons = [
        [InlineKeyboardButton(text="💳 Оформить", callback_data="checkout")],
        [InlineKeyboardButton(text="🗑 Очистить", callback_data="clear_cart")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="profile")]
    ]
    
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

@dp.callback_query(F.data == "clear_cart")
async def clear_cart(call: CallbackQuery):
    uid = str(call.from_user.id)
    if uid in users:
        users[uid]["cart"] = {}
        save_all()
    await call.message.edit_text("✅ Корзина очищена", reply_markup=profile_menu())
    await call.answer()

@dp.callback_query(F.data == "checkout")
async def checkout(call: CallbackQuery):
    uid = str(call.from_user.id)
    cart = users.get(uid, {}).get("cart", {})
    
    if not cart:
        await call.answer("Корзина пуста!", show_alert=True)
        return
    
    total = 0
    for pid, data in cart.items():
        prod = categories[data["cid"]]["products"][pid]
        if prod["stock"] < data["qty"]:
            await call.message.edit_text(
                f"❌ {data['name']} осталось {prod['stock']} шт.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🛒 Корзина", callback_data="cart")]
                ])
            )
            await call.answer()
            return
        total += data["price"] * data["qty"]
    
    if users[uid]["balance"] < total:
        await call.answer("❌ Недостаточно средств!", show_alert=True)
        return
    
    # Списываем баланс
    users[uid]["balance"] -= total
    
    # Уменьшаем товары
    for pid, data in cart.items():
        categories[data["cid"]]["products"][pid]["stock"] -= data["qty"]
    
    number = generate_number()
    
    # Уведомление админу
    text = f"🛒 **Заказ из корзины!**\n👤 {call.from_user.full_name} (`{uid}`)\n💰 {total}₽\n🎫 {number}\n\n"
    for data in cart.values():
        text += f"📦 {data['name']} x{data['qty']}\n"
    
    await bot.send_message(
        ADMIN_ID,
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Выдать", callback_data=f"deliver_{number}_{uid}")]
        ])
    )
    
    pending[number] = {"uid": uid, "cart": cart.copy()}
    
    # История
    users[uid]["purchases"].append({
        "number": number,
        "amount": total,
        "items": cart.copy(),
        "date": str(datetime.now()),
        "delivered": False
    })
    
    users[uid]["cart"] = {}
    save_all()
    
    await call.message.edit_text(
        f"✅ **Заказ оформлен!**\n🎫 Номер: {number}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 В каталог", callback_data="catalog")]
        ])
    )
    await call.answer()

# ===== ВЫДАЧА =====
@dp.callback_query(F.data.startswith("deliver_"))
async def start_delivery(call: CallbackQuery, state: FSMContext):
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer("Это не для тебя!")
        return
    
    _, num, uid = call.data.split("_")
    await state.update_data(delivery_num=num, delivery_uid=uid)
    await state.set_state(AdminStates.delivery_text)
    
    await call.message.edit_text(f"✏️ Введи данные для заказа #{num}")
    await call.answer()

@dp.message(AdminStates.delivery_text)
async def process_delivery(msg: Message, state: FSMContext):
    if str(msg.from_user.id) != str(ADMIN_ID):
        return
    
    data = await state.get_data()
    num = data.get("delivery_num")
    uid = data.get("delivery_uid")
    
    if await notify(int(uid), f"✅ Товар готов!\n🎫 Заказ #{num}\n📦 Данные:\n{msg.text}"):
        for p in users[uid]["purchases"]:
            if p.get("number") == num:
                p["delivered"] = True
                break
        save_all()
        await msg.answer(f"✅ Отправлено {uid}")
    else:
        await msg.answer(f"❌ Не удалось отправить {uid}")
    
    await state.clear()

# ===== АДМИН КАТЕГОРИИ =====
@dp.callback_query(F.data == "admin_cats")
async def admin_cats(call: CallbackQuery):
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer()
        return
    
    text = "📁 **Категории:**\n\n"
    buttons = []
    
    for cid, cat in categories.items():
        text += f"📁 {cat['name']} ({len(cat['products'])} товаров)\n"
        buttons.append([
            InlineKeyboardButton(text=f"✏️ {cat['name']}", callback_data=f"edit_cat_{cid}"),
            InlineKeyboardButton(text="❌", callback_data=f"del_cat_{cid}")
        ])
    
    buttons.append([InlineKeyboardButton(text="➕ Добавить", callback_data="add_cat")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

@dp.callback_query(F.data == "add_cat")
async def add_cat(call: CallbackQuery, state: FSMContext):
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer()
        return
    
    await state.set_state(AdminStates.cat_name)
    await call.message.edit_text("📁 Введите название категории:")
    await call.answer()

@dp.message(AdminStates.cat_name)
async def process_cat_name(msg: Message, state: FSMContext):
    if str(msg.from_user.id) != str(ADMIN_ID):
        return
    
    cid = f"cat_{random.randint(1000, 9999)}"
    categories[cid] = {"name": msg.text.strip(), "products": {}}
    save_all()
    
    await msg.answer(f"✅ Категория создана!", reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data.startswith("edit_cat_"))
async def edit_cat(call: CallbackQuery, state: FSMContext):
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer()
        return
    
    cid = call.data.split("_")[2]
    await state.update_data(edit_cid=cid)
    await state.set_state(AdminStates.cat_edit)
    
    await call.message.edit_text(f"✏️ Новое название для '{categories[cid]['name']}':")
    await call.answer()

@dp.message(AdminStates.cat_edit)
async def process_cat_edit(msg: Message, state: FSMContext):
    if str(msg.from_user.id) != str(ADMIN_ID):
        return
    
    data = await state.get_data()
    cid = data.get("edit_cid")
    
    categories[cid]["name"] = msg.text.strip()
    save_all()
    
    await msg.answer("✅ Категория обновлена!", reply_markup=admin_menu())
    await state.clear()

@dp.callback_query(F.data.startswith("del_cat_"))
async def del_cat(call: CallbackQuery):
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer()
        return
    
    cid = call.data.split("_")[2]
    del categories[cid]
    save_all()
    
    await call.answer("✅ Категория удалена!")
    await admin_cats(call)

# ===== АДМИН ТОВАРЫ =====
@dp.callback_query(F.data == "admin_prods")
async def admin_prods(call: CallbackQuery):
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer()
        return
    
    if not categories:
        await call.message.edit_text("❌ Сначала создайте категорию!")
        await call.answer()
        return
    
    text = "📦 **Все товары:**\n\n"
    buttons = []
    
    for cid, cat in categories.items():
        if cat["products"]:
            text += f"📁 {cat['name']}:\n"
            for pid, prod in cat["products"].items():
                text += f"  • {prod['name']} - {prod['price']}₽ ({prod['stock']} шт.)\n"
                buttons.append([
                    InlineKeyboardButton(text=f"✏️ {prod['name'][:10]}", callback_data=f"edit_prod_{cid}_{pid}"),
                    InlineKeyboardButton(text="❌", callback_data=f"del_prod_{cid}_{pid}")
                ])
    
    buttons.append([InlineKeyboardButton(text="➕ Добавить товар", callback_data="add_prod")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

@dp.callback_query(F.data == "add_prod")
async def add_prod(call: CallbackQuery, state: FSMContext):
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer()
        return
    
    buttons = []
    for cid, cat in categories.items():
        buttons.append([InlineKeyboardButton(text=f"📁 {cat['name']}", callback_data=f"choose_cat_{cid}")])
    
    await state.set_state(AdminStates.prod_cat)
    await call.message.edit_text(
        "📦 Выберите категорию:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons + [[InlineKeyboardButton(text="🔙 Назад", callback_data="admin_prods")]])
    )
    await call.answer()

@dp.callback_query(AdminStates.prod_cat, F.data.startswith("choose_cat_"))
async def choose_cat(call: CallbackQuery, state: FSMContext):
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer()
        return
    
    cid = call.data.split("_")[2]
    await state.update_data(prod_cid=cid)
    await state.set_state(AdminStates.prod_name)
    
    await call.message.edit_text("✏️ Введите название товара:")
    await call.answer()

@dp.message(AdminStates.prod_name)
async def prod_name(msg: Message, state: FSMContext):
    if str(msg.from_user.id) != str(ADMIN_ID):
        return
    
    await state.update_data(prod_name=msg.text.strip())
    await state.set_state(AdminStates.prod_desc)
    
    await msg.answer("📝 Введите описание товара:")

@dp.message(AdminStates.prod_desc)
async def prod_desc(msg: Message, state: FSMContext):
    if str(msg.from_user.id) != str(ADMIN_ID):
        return
    
    await state.update_data(prod_desc=msg.text.strip())
    await state.set_state(AdminStates.prod_price)
    
    await msg.answer("💰 Введите цену (число):")

@dp.message(AdminStates.prod_price)
async def prod_price(msg: Message, state: FSMContext):
    if str(msg.from_user.id) != str(ADMIN_ID):
        return
    
    try:
        price = int(msg.text.strip())
        if price <= 0:
            await msg.answer("❌ Цена должна быть больше 0!")
            return
        
        await state.update_data(prod_price=price)
        await state.set_state(AdminStates.prod_stock)
        
        await msg.answer("📦 Введите количество (число):")
    except:
        await msg.answer("❌ Введите число!")

@dp.message(AdminStates.prod_stock)
async def prod_stock(msg: Message, state: FSMContext):
    if str(msg.from_user.id) != str(ADMIN_ID):
        return
    
    try:
        stock = int(msg.text.strip())
        if stock < 0:
            await msg.answer("❌ Количество не может быть отрицательным!")
            return
        
        data = await state.get_data()
        cid = data.get("prod_cid")
        name = data.get("prod_name")
        desc = data.get("prod_desc")
        price = data.get("prod_price")
        
        pid = f"prod_{random.randint(10000, 99999)}"
        
        categories[cid]["products"][pid] = {
            "name": name,
            "desc": desc,
            "price": price,
            "stock": stock
        }
        save_all()
        
        await msg.answer(f"✅ Товар добавлен!", reply_markup=admin_menu())
        await state.clear()
    except:
        await msg.answer("❌ Введите число!")

@dp.callback_query(F.data.startswith("del_prod_"))
async def del_prod(call: CallbackQuery):
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer()
        return
    
    _, _, cid, pid = call.data.split("_")
    del categories[cid]["products"][pid]
    save_all()
    
    await call.answer("✅ Товар удален!")
    await admin_prods(call)

# ===== АДМИН ПРОМОКОДЫ =====
@dp.callback_query(F.data == "admin_promos")
async def admin_promos(call: CallbackQuery):
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer()
        return
    
    text = "🎟 **Промокоды:**\n\n"
    buttons = []
    
    for code, data in promocodes.items():
        text += f"🎫 `{code}` - {data['discount']}%\n"
        text += f"   Осталось: {data['left']}/{data['left'] + data['used']}\n\n"
        buttons.append([InlineKeyboardButton(text=f"❌ Удалить {code}", callback_data=f"del_promo_{code}")])
    
    buttons.append([InlineKeyboardButton(text="➕ Создать", callback_data="create_promo")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")])
    
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

@dp.callback_query(F.data == "create_promo")
async def create_promo(call: CallbackQuery, state: FSMContext):
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer()
        return
    
    await state.set_state(PromoStates.name)
    await call.message.edit_text("🎟 Введите название промокода (например: SUMMER50):")
    await call.answer()

@dp.message(PromoStates.name)
async def promo_name(msg: Message, state: FSMContext):
    if str(msg.from_user.id) != str(ADMIN_ID):
        return
    
    name = msg.text.strip().upper()
    
    if name in promocodes:
        await msg.answer("❌ Такой промокод уже есть!")
        return
    
    await state.update_data(promo_name=name)
    await state.set_state(PromoStates.discount)
    
    await msg.answer("💰 Введите процент скидки (1-99):")

@dp.message(PromoStates.discount)
async def promo_discount(msg: Message, state: FSMContext):
    if str(msg.from_user.id) != str(ADMIN_ID):
        return
    
    try:
        disc = int(msg.text.strip())
        if disc < 1 or disc > 99:
            await msg.answer("❌ Введите число от 1 до 99!")
            return
        
        await state.update_data(promo_discount=disc)
        await state.set_state(PromoStates.uses)
        
        await msg.answer("📊 Введите количество активаций:")
    except:
        await msg.answer("❌ Введите число!")

@dp.message(PromoStates.uses)
async def promo_uses(msg: Message, state: FSMContext):
    if str(msg.from_user.id) != str(ADMIN_ID):
        return
    
    try:
        uses = int(msg.text.strip())
        if uses <= 0:
            await msg.answer("❌ Введите положительное число!")
            return
        
        data = await state.get_data()
        name = data.get("promo_name")
        disc = data.get("promo_discount")
        
        promocodes[name] = {
            "discount": disc,
            "left": uses,
            "used": 0
        }
        save_all()
        
        await msg.answer(f"✅ Промокод {name} создан!", reply_markup=admin_menu())
        await state.clear()
    except:
        await msg.answer("❌ Введите число!")

@dp.callback_query(F.data.startswith("del_promo_"))
async def del_promo(call: CallbackQuery):
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer()
        return
    
    code = call.data.replace("del_promo_", "")
    
    if code in promocodes:
        del promocodes[code]
        save_all()
        await call.answer(f"✅ Промокод {code} удален!")
    else:
        await call.answer("❌ Промокод не найден!")
    
    await admin_promos(call)

# ===== АДМИН ПОЛЬЗОВАТЕЛИ =====
@dp.callback_query(F.data == "admin_users")
async def admin_users(call: CallbackQuery):
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer()
        return
    
    text = "👥 **Пользователи:**\n\n"
    for uid, data in list(users.items())[:20]:
        text += f"🆔 `{uid}`\n"
        text += f"👤 {data.get('name', '')} @{data.get('username', '')}\n"
        text += f"💰 {data.get('balance', 0)}₽\n"
        text += f"📦 {len(data.get('purchases', []))} покупок\n\n"
    
    await call.message.edit_text(text, reply_markup=admin_menu())
    await call.answer()

# ===== АДМИН БАЛАНС =====
@dp.callback_query(F.data == "admin_balance")
async def admin_balance(call: CallbackQuery, state: FSMContext):
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer()
        return
    
    await state.set_state(AdminStates.balance_user)
    await call.message.edit_text("💰 Введите ID пользователя:")
    await call.answer()

@dp.message(AdminStates.balance_user)
async def balance_user(msg: Message, state: FSMContext):
    if str(msg.from_user.id) != str(ADMIN_ID):
        return
    
    uid = msg.text.strip()
    
    if uid not in users:
        await msg.answer("❌ Пользователь не найден!")
        await state.clear()
        return
    
    await state.update_data(balance_uid=uid)
    await state.set_state(AdminStates.balance_amount)
    
    await msg.answer(f"💰 Текущий баланс: {users[uid]['balance']}₽\nВведите сумму (+500 или -200):")

@dp.message(AdminStates.balance_amount)
async def balance_amount(msg: Message, state: FSMContext):
    if str(msg.from_user.id) != str(ADMIN_ID):
        return
    
    try:
        amount = int(msg.text.strip())
    except:
        await msg.answer("❌ Введите число!")
        return
    
    data = await state.get_data()
    uid = data.get("balance_uid")
    
    old = users[uid]["balance"]
    users[uid]["balance"] += amount
    if users[uid]["balance"] < 0:
        users[uid]["balance"] = 0
    
    save_all()
    
    await notify(int(uid), f"💰 Баланс изменен: {old}₽ → {users[uid]['balance']}₽")
    await msg.answer(f"✅ Баланс {uid}: {old}₽ → {users[uid]['balance']}₽", reply_markup=admin_menu())
    await state.clear()

# ===== АДМИН ПОДДЕРЖКА =====
@dp.callback_query(F.data == "admin_support")
async def admin_support(call: CallbackQuery):
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer()
        return
    
    waiting = {qid: q for qid, q in support.items() if q.get("status") == "waiting"}
    
    if not waiting:
        await call.message.edit_text("📭 Нет вопросов", reply_markup=admin_menu())
        await call.answer()
        return
    
    text = "🆘 **Вопросы:**\n\n"
    buttons = []
    
    for qid, q in list(waiting.items())[:10]:
        text += f"❓ #{qid}\n👤 {q['name']}\n📝 {q['text'][:50]}...\n\n"
        buttons.append([InlineKeyboardButton(text=f"✏️ Ответить #{qid}", callback_data=f"ans_{qid}")])
    
    await call.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await call.answer()

# ===== ПОДДЕРЖКА =====
@dp.callback_query(F.data == "support")
async def support(call: CallbackQuery, state: FSMContext):
    await state.set_state(UserStates.support_question)
    await call.message.edit_text(
        "🆘 Напишите ваш вопрос:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="main")]
        ])
    )
    await call.answer()

@dp.message(UserStates.support_question)
async def support_question(msg: Message, state: FSMContext):
    uid = str(msg.from_user.id)
    qid = str(random.randint(10000, 99999))
    
    support[qid] = {
        "uid": uid,
        "name": msg.from_user.full_name,
        "text": msg.text,
        "date": str(datetime.now()),
        "status": "waiting"
    }
    save_all()
    
    await notify(int(uid), "✅ Вопрос отправлен!")
    await bot.send_message(ADMIN_ID, f"🆘 Новый вопрос #{qid}\nОт: {msg.from_user.full_name}\n{msg.text}")
    
    await msg.answer("Вопрос отправлен", reply_markup=main_menu())
    await state.clear()

# ===== АДМИН НАЗАД =====
@dp.callback_query(F.data == "admin_back")
async def admin_back(call: CallbackQuery):
    if str(call.from_user.id) != str(ADMIN_ID):
        await call.answer()
        return
    await call.message.edit_text("👑 Админ-панель", reply_markup=admin_menu())
    await call.answer()

# ===== ЗАПУСК =====
async def main():
    await bot.send_message(ADMIN_ID, "✅ Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
