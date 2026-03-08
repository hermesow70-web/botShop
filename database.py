import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

def load_data(filename: str) -> Any:
    """Загрузка данных из JSON файла"""
    try:
        with open(DATA_DIR / f"{filename}.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        if filename == "queue":
            return []
        return {}

def save_data(filename: str, data: Any) -> None:
    """Сохранение данных в JSON файл"""
    with open(DATA_DIR / f"{filename}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ========== ГЛОБАЛЬНЫЕ ДАННЫЕ ==========
users = load_data("users")
admins = load_data("admins")
dialogs = load_data("dialogs")
waiting_queue = load_data("queue")
pending_by_tag = load_data("pending_by_tag")
banlist = load_data("banlist")
mutelist = load_data("mutelist")
complaints = load_data("complaints")

def save_all():
    """Сохранить все данные"""
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
    role = admins[str(user_id)].get("role", "")
    return role in ["ГЛ АДМИН", "СОВЛАДЕЛЕЦ", "ВЛАДЕЛЕЦ"]

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID

def is_banned(user_id: int) -> bool:
    return str(user_id) in banlist

def is_muted(user_id: int) -> bool:
    if str(user_id) not in mutelist:
        return False
    try:
        mute_until = datetime.fromisoformat(mutelist[str(user_id)]["until"])
        if datetime.now() > mute_until:
            del mutelist[str(user_id)]
            save_all()
            return False
        return True
    except:
        return False

def get_user_name(user_id: int) -> str:
    return users.get(str(user_id), {}).get("name", "Пользователь")

def get_admin_tag(user_id: int) -> str:
    return admins.get(str(user_id), {}).get("tag", "#unknown")
