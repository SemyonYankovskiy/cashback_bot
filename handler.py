# --- handler.py ---
from aiogram import types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

from database import register_user, get_banks, get_categories, insert_cashback, get_user_friend, set_user_friend, \
    delete_all_cashbacks, get_user_bank_category_pairs, \
    delete_cashback_entries
from core import determine_period, format_cashbacks, get_next_two_periods, delete_menu_keyboard, \
    confirm_all_deletion_keyboard, bank_category_selection_keyboard


class MenuState(StatesGroup):
    selecting_bank = State()
    selecting_category = State()
    selecting_percent = State()
    selecting_period = State()


class FriendState(StatesGroup):
    waiting_for_friend = State()


class DeleteStates(StatesGroup):
    choosing_category = State()
    confirming_all = State()


def main_menu_keyboard():
    return ReplyKeyboardMarkup(resize_keyboard=True).add(
        KeyboardButton("📊 Показать мой кешбек"),
        KeyboardButton("🤝 Показать наш кешбек")
    )


def get_exit_button():
    return InlineKeyboardButton("✖️ Выход", callback_data="exit")


def register_handlers(dp):
    @dp.message_handler(commands="start")
    async def start_cmd(msg: types.Message):
        print(f"{msg.from_user.username}, commands='start'")
        await register_user(msg.from_user.id)
        await msg.answer("Добро пожаловать!", reply_markup=main_menu_keyboard())

    # Обработка выхода через кнопку
    @dp.callback_query_handler(lambda c: c.data == "exit", state='*')
    async def exit_process(call: types.CallbackQuery, state: FSMContext):
        await state.finish()
        await call.message.edit_text("Отменено", reply_markup=None)
        await call.answer()  # чтобы убрать "часики" у кнопки

    @dp.message_handler(commands="add")
    async def add_cashback(msg: types.Message, state: FSMContext):
        print(f"{msg.from_user.username}, commands='add'")
        banks = await get_banks()
        markup = InlineKeyboardMarkup(row_width=1)
        for bid, name in banks:
            markup.add(InlineKeyboardButton(name, callback_data=f"bank_{bid}"))
        markup.add(get_exit_button())
        await msg.answer("Выберите банк:", reply_markup=markup)
        await state.set_state(MenuState.selecting_bank)

    @dp.callback_query_handler(lambda c: c.data.startswith("bank_"), state=MenuState.selecting_bank)
    async def choose_bank(call: types.CallbackQuery, state: FSMContext):
        bid = int(call.data.split("_")[1])
        await state.update_data(bank_id=bid)
        cats = await get_categories()
        markup = InlineKeyboardMarkup(row_width=1)
        for cid, name in cats:
            markup.add(InlineKeyboardButton(name, callback_data=f"cat_{cid}"))
        # Добавляем кнопку "Выход"
        markup.add(
            InlineKeyboardButton("🔙 Назад", callback_data="back_to_bank"),
            get_exit_button()
        )
        await call.message.edit_text("Выберите категорию:", reply_markup=markup)
        await state.set_state(MenuState.selecting_category)

    @dp.callback_query_handler(lambda c: c.data == "back_to_bank", state=MenuState.selecting_category)
    async def back_to_bank(call: types.CallbackQuery, state: FSMContext):
        banks = await get_banks()
        markup = InlineKeyboardMarkup(row_width=1)
        for bid, name in banks:
            markup.add(InlineKeyboardButton(name, callback_data=f"bank_{bid}"))
        markup.add(get_exit_button())
        await call.message.edit_text("Выберите банк:", reply_markup=markup)
        await state.set_state(MenuState.selecting_bank)
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("cat_"), state=MenuState.selecting_category)
    async def choose_category(call: types.CallbackQuery, state: FSMContext):
        cid = int(call.data.split("_")[1])
        await state.update_data(category_id=cid)
        markup = InlineKeyboardMarkup()
        for row in [[1, 2, 3], [4, 5, 6], [7, 8, 9], [10, 15]]:
            markup.row(*[InlineKeyboardButton(f"{p}%", callback_data=f"percent_{p}") for p in row])
        # Кнопки назад и выход
        markup.row(
            InlineKeyboardButton("🔙 Назад", callback_data="back_to_category"),
            get_exit_button()
        )
        await call.message.edit_text("Выберите процент:", reply_markup=markup)
        await state.set_state(MenuState.selecting_percent)
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data == "back_to_category", state=MenuState.selecting_percent)
    async def back_to_category(call: types.CallbackQuery, state: FSMContext):
        cats = await get_categories()
        markup = InlineKeyboardMarkup(row_width=1)
        for cid, name in cats:
            markup.add(InlineKeyboardButton(name, callback_data=f"cat_{cid}"))
        markup.add(
            InlineKeyboardButton("🔙 Назад", callback_data="back_to_bank"),
            get_exit_button()
        )
        await call.message.edit_text("Выберите категорию:", reply_markup=markup)
        await state.set_state(MenuState.selecting_category)
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("percent_"), state=MenuState.selecting_percent)
    async def choose_percent(call: types.CallbackQuery, state: FSMContext):
        pct = float(call.data.split("_")[1])
        await state.update_data(percent=pct)
        data = await state.get_data()
        period = await determine_period(call.from_user.id, data['bank_id'], data['category_id'])
        if period:
            await insert_cashback(call.from_user.id, data['bank_id'], data['category_id'], pct, period)
            await call.message.edit_text("Кешбек добавлен!", reply_markup=None)
            await state.finish()
        else:
            cur, nxt = get_next_two_periods()
            markup = InlineKeyboardMarkup().add(
                InlineKeyboardButton(f"Текущий ({cur})", callback_data=f"period_{cur}"),
                InlineKeyboardButton(f"Следующий ({nxt})", callback_data=f"period_{nxt}"),
                get_exit_button()
            )
            await call.message.edit_text("Выберите период:", reply_markup=markup)
            await state.set_state(MenuState.selecting_period)
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data.startswith("period_"), state=MenuState.selecting_period)
    async def choose_period(call: types.CallbackQuery, state: FSMContext):
        period = call.data.split("_")[1]
        data = await state.get_data()
        await insert_cashback(call.from_user.id, data['bank_id'], data['category_id'], data['percent'], period)
        await call.message.edit_text("Кешбек добавлен!", reply_markup=None)
        await state.finish()
        await call.answer()

    @dp.message_handler(lambda m: m.text == "📊 Показать мой кешбек")
    async def my_cashbacks(msg: types.Message):
        print(f"{msg.from_user.username}, commands='📊 Показать мой кешбек'")
        text = await format_cashbacks(msg.from_user.id)
        await msg.answer(text)

    @dp.message_handler(lambda m: m.text == "🤝 Показать наш кешбек")
    async def shared_cashbacks(msg: types.Message):
        print(f"{msg.from_user.username}, commands='🤝 Показать наш кешбек'")
        uid = msg.from_user.id
        fid = await get_user_friend(uid)
        if not fid:
            return await msg.answer("У вас нет друга.")
        utext = await format_cashbacks(uid)
        ftext = await format_cashbacks(fid)
        await msg.answer(f"Ваш кешбек:\n{utext}")
        await msg.answer(f"Кешбек друга:\n{ftext}")

    @dp.message_handler(commands=["addfriend"])
    async def add_friend_start(msg: types.Message, state: FSMContext):
        markup = InlineKeyboardMarkup().add(get_exit_button())
        await msg.answer(
            "Введите Telegram ID вашего друга (число) или нажмите кнопку 'Выход', чтобы отменить.",
            reply_markup=markup
        )
        await state.set_state(FriendState.waiting_for_friend)

    @dp.message_handler(lambda m: m.text == "➕ Добавить друга")
    async def add_friend_from_menu(msg: types.Message):
        await add_friend_start(msg, None)

    @dp.message_handler(state=FriendState.waiting_for_friend)
    async def add_friend_process(msg: types.Message, state: FSMContext):
        text = msg.text.strip()
        # Убираем проверку на 'отмена', теперь отмена через кнопку
        try:
            friend_id = int(text)
        except ValueError:
            await msg.answer("Неверный формат. Введите числовой Telegram ID.")
            return

        if friend_id == msg.from_user.id:
            await msg.answer("Нельзя добавить самого себя.")
            return

        await set_user_friend(msg.from_user.id, friend_id)
        await state.finish()
        await msg.answer("Друг успешно добавлен!", reply_markup=main_menu_keyboard())

    @dp.message_handler(commands=["delete"])
    async def delete_menu(msg: types.Message):
        await msg.answer("Что вы хотите удалить?", reply_markup=delete_menu_keyboard())

    @dp.callback_query_handler(lambda c: c.data == "delete_by_categories")
    async def delete_by_bank_category(call: types.CallbackQuery, state: FSMContext):
        pairs = await get_user_bank_category_pairs(call.from_user.id)
        if not pairs:
            await call.answer("Нет кешбеков для удаления", show_alert=True)
            return
        await state.update_data(selected=[])
        await state.set_state(DeleteStates.choosing_category)
        await call.message.edit_text("Выберите кешбеки для удаления:",
                                     reply_markup=bank_category_selection_keyboard(pairs))

    @dp.callback_query_handler(lambda c: c.data.startswith("delpair_"), state=DeleteStates.choosing_category)
    async def select_pair_to_delete(call: types.CallbackQuery, state: FSMContext):
        data = await state.get_data()
        selected = data.get("selected", [])
        entry_id_str = call.data.split("_")[1]

        if entry_id_str == "done":
            await delete_cashback_entries(call.from_user.id, selected)
            await state.finish()
            await call.message.edit_text("Выбранные кешбеки удалены.")
            return

        entry_id = int(entry_id_str)
        if entry_id in selected:
            selected.remove(entry_id)
        else:
            selected.append(entry_id)

        await state.update_data(selected=selected)
        pairs = await get_user_bank_category_pairs(call.from_user.id)
        await call.message.edit_reply_markup(reply_markup=bank_category_selection_keyboard(pairs, selected))
        await call.answer()

    @dp.callback_query_handler(lambda c: c.data == "delete_all_cashbacks")
    async def confirm_delete_all_menu(call: types.CallbackQuery, state: FSMContext):
        await state.set_state(DeleteStates.confirming_all)
        await call.message.edit_text("Вы уверены, что хотите удалить все кешбеки?",
                                     reply_markup=confirm_all_deletion_keyboard())

    @dp.callback_query_handler(lambda c: c.data == "confirm_delete_all", state=DeleteStates.confirming_all)
    async def confirm_delete_all(call: types.CallbackQuery, state: FSMContext):
        await delete_all_cashbacks(call.from_user.id)
        await state.finish()
        await call.message.edit_text("✅ Все кешбеки удалены.")

    @dp.callback_query_handler(lambda c: c.data == "cancel_delete_all", state=DeleteStates.confirming_all)
    async def cancel_delete_all(call: types.CallbackQuery, state: FSMContext):
        await state.finish()
        await call.message.edit_text("Удаление отменено.")
