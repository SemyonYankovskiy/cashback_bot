# --- core.py ---
from datetime import datetime

from database import get_cashbacks, get_user_all_periods
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


MONTHS_RU = {
    1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель', 5: 'Май', 6: 'Июнь',
    7: 'Июль', 8: 'Август', 9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
}


def get_next_two_periods():
    now = datetime.now()
    current = now.strftime("%Y-%m")
    year, month = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    next_ = datetime(year, month, 1).strftime("%Y-%m")
    return current, next_


async def determine_period(user_id, bank_id, category_id):
    periods = await get_user_all_periods(user_id, bank_id, category_id)
    current, next_ = get_next_two_periods()
    if current in periods and next_ in periods:
        return None
    return next_ if current in periods else current


async def format_cashbacks(user_id):
    rows = await get_cashbacks(user_id)
    if not rows:
        return "Кешбеков нет."

    grouped = {}
    for period, bank, category, percent in rows:
        grouped.setdefault(period, []).append((bank, category, percent))

    lines = []
    for period in sorted(grouped):
        y, m = map(int, period.split('-'))
        lines.append(f"Кешбеки на {MONTHS_RU.get(m, str(m))}:\n")

        bank_lines = {}
        for bank, cat, pct in grouped[period]:
            bank_lines.setdefault(bank, []).append((cat, pct))

        for bank, cats in bank_lines.items():
            lines.append(f"🏦 {bank}")
            lines.append("------------------------")
            for cat, pct in cats:
                formatted_pct = f"{int(pct)}%" if pct == int(pct) else f"{pct:.1f}%"
                lines.append(f"{cat}: {formatted_pct}")
            lines.append("")

    return "\n".join(lines).strip()




def delete_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🗂 Удалить по категориям", callback_data="delete_by_categories")],
        [InlineKeyboardButton("💣 Удалить все кешбеки", callback_data="delete_all_cashbacks")],
        [InlineKeyboardButton("✖️ Выход", callback_data="exit")]
    ])


def bank_category_selection_keyboard(pairs, selected_ids=None):
    if selected_ids is None:
        selected_ids = []
    markup = InlineKeyboardMarkup(row_width=1)
    for entry_id, bank_name, cat_name, percent in pairs:
        prefix = "✅ " if entry_id in selected_ids else ""
        text = f"{prefix}{bank_name} → {cat_name}: {percent:.0f}%"
        markup.add(InlineKeyboardButton(text, callback_data=f"delpair_{entry_id}"))
    markup.add(InlineKeyboardButton("⁉️ Удалить выбранные", callback_data="delpair_done"))
    markup.add(InlineKeyboardButton("✖️ Отмена", callback_data="exit"))
    return markup


def confirm_all_deletion_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_delete_all")],
        [InlineKeyboardButton("✖️ Отмена", callback_data="cancel_delete_all")]
    ])