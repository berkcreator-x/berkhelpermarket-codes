from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from src.payments import GENERATION_PACKAGES


def main_menu_keyboard(
    is_admin: bool = False,
) -> ReplyKeyboardMarkup:

    rows = [
        [
            KeyboardButton(text="🛠 Инструменты"),
        ],
        [
            KeyboardButton(text="👤 Профиль"),
            KeyboardButton(text="💳 Генерации"),
        ],
    ]

    if is_admin:
        rows.append(
            [
                KeyboardButton(text="⚙️ Панель"),
            ]
        )

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
    )


def tools_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Подменю инструментов создания/улучшения карточек.

    Сюда же в будущем добавляются новые функции
    (улучшение фото, генерация баннеров и т.д.) —
    без необходимости менять главное меню.
    """

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🆕 Новый товар",
                    callback_data="tools:new",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✨ Улучшить товар",
                    callback_data="tools:improve",
                ),
            ],
        ]
    )


def profile_nav_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Моя статистика",
                    callback_data="profile_nav:stats",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="📜 История генераций",
                    callback_data="profile_nav:history",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🛒 История покупок",
                    callback_data="profile_nav:purchases",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👤 Профиль",
                    callback_data="profile_nav:profile",
                ),
            ],
        ]
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="❌ Отмена"),
            ],
            [
                KeyboardButton(text="🏠 Главное меню"),
            ],
        ],
        resize_keyboard=True,
    )


def generation_packages_keyboard() -> InlineKeyboardMarkup:
    """
    ВАЖНО:
    GENERATION_PACKAGES — это dict.

    Поэтому обязательно итерируемся по values(),
    иначе pkg станет строкой ("start"),
    что и вызывает ошибку:

        'str' object has no attribute 'price_rub'
    """

    buttons = [
        [
            InlineKeyboardButton(
                text=f"{package.title} — {package.price_rub} ₽",
                callback_data=f"buy_package:{package.id}",
            )
        ]
        for package in GENERATION_PACKAGES.values()
    ]

    return InlineKeyboardMarkup(
        inline_keyboard=buttons,
    )


def payment_check_keyboard(
    label: str,
) -> InlineKeyboardMarkup:

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Я оплатил",
                    callback_data=f"check_payment:{label}",
                )
            ]
        ]
    )


def admin_panel_keyboard() -> InlineKeyboardMarkup:

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Статистика",
                    callback_data="admin:stats",
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Пользователи",
                    callback_data="admin:users:0",
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ Выдать генерации",
                    callback_data="admin:grant",
                )
            ],
        ]
    )


def admin_users_pagination_keyboard(
    offset: int,
    has_more: bool,
) -> InlineKeyboardMarkup:

    buttons: list[list[InlineKeyboardButton]] = []

    nav_row: list[InlineKeyboardButton] = []

    if offset > 0:
        nav_row.append(
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"admin:users:{max(offset - 10, 0)}",
            )
        )

    if has_more:
        nav_row.append(
            InlineKeyboardButton(
                text="Вперёд ➡️",
                callback_data=f"admin:users:{offset + 10}",
            )
        )

    if nav_row:
        buttons.append(nav_row)

    buttons.append(
        [
            InlineKeyboardButton(
                text="⬅️ В меню админа",
                callback_data="admin:menu",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=buttons,
    )
