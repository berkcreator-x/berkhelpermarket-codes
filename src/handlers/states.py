from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class NewProductStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_category = State()
    waiting_for_features = State()
    waiting_for_audience = State()


class ImproveProductStates(StatesGroup):
    waiting_for_text = State()


class AdminGrantStates(StatesGroup):
    waiting_for_telegram_id = State()
    waiting_for_amount = State()
