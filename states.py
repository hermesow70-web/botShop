from aiogram.fsm.state import State, StatesGroup

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
