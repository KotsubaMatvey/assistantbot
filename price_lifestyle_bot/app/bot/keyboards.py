from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

STORE_LABELS = {
    "smart": "Smart",
    "magnit": "Магнит",
    "spar": "SPAR",
    "pyaterochka": "Пятёрочка",
    "fix_price": "Fix Price",
}

MODE_LABELS = {
    "strict": "Строгий",
    "similar": "Похожие",
    "mixed": "Смешанный",
}


def settings_keyboard(enabled: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for slug, label in STORE_LABELS.items():
        mark = "✅" if slug in enabled else "⬜"
        rows.append([InlineKeyboardButton(text=f"{mark} {label}", callback_data=f"store:{slug}")])
    rows.append(
        [
            InlineKeyboardButton(text="Smart карта", callback_data="card:smart"),
            InlineKeyboardButton(text="Магнит карта", callback_data="card:magnit"),
        ]
    )
    rows.append(
        [
            InlineKeyboardButton(text="SPAR карта", callback_data="card:spar"),
            InlineKeyboardButton(text="X5 карта", callback_data="card:pyaterochka"),
        ]
    )
    rows.append([InlineKeyboardButton(text="Fix Price карта", callback_data="card:fix_price")])
    rows.append(
        [
            InlineKeyboardButton(text="Strict", callback_data="mode:strict"),
            InlineKeyboardButton(text="Similar", callback_data="mode:similar"),
            InlineKeyboardButton(text="Mixed", callback_data="mode:mixed"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)

