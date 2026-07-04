from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from src.payments import GENERATION_PACKAGES


def main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="🆕 Новый товар"), KeyboardButton(text="✨ Улучшить товар")],
        [KeyboardButton(text="👤 Профиль"), KeyboardButton(text="💳 Генерации")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="⚙️ Панель")])

    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def cancel_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="❌ Отмена")],
            [KeyboardButton(text="🏠 Главное меню")],
        ],
        resize_keyboard=True,
    )


def generation_packages_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=f"{pkg.title} — {pkg.price_rub:.0f}₽",
                callback_data=f"buy_package:{pkg.id}",
            )
        ]
        for pkg in GENERATION_PACKAGES
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def payment_check_keyboard(label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я оплатил", callback_data=f"check_payment:{label}")]
        ]
    )


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
            [InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users:0")],
            [InlineKeyboardButton(text="➕ Выдать генерации", callback_data="admin:grant")],
        ]
    )


def admin_users_pagination_keyboard(offset: int, has_more: bool) -> InlineKeyboardMarkup:
    buttons = []
    nav_row = []
    if offset > 0:
        nav_row.append(
            InlineKeyboardButton(text="⬅️ Назад", callback_data=f"admin:users:{max(offset - 10, 0)}")
        )
    if has_more:
        nav_row.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"admin:users:{offset + 10}"))
    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(text="⬅️ В меню админа", callback_data="admin:menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
