import telebot
from telebot import types
import datetime
from db import init_db
from logic import create_new_game, close_game, get_active_game, get_game_date, get_last_game, get_game_stat, validate_game_balance, \
    get_all_players, get_active_players, get_potential_players, get_player, get_players_stat, \
    create_player, add_player, exit_player, add_buyin, update_exit_chips, \
    calculate_payments, execute_payment
from config import TOKEN, CURRENCY

# === Инициализация ===
if not TOKEN:
    raise RuntimeError("❌ Не задан TOKEN. Укажи переменную окружения POKER_BOT_TOKEN.")

bot = telebot.TeleBot(TOKEN)
init_db()

# ReplyKeyboard кнопка "Главное меню"
def main_reply_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("📋 Главное меню"))
    return markup

# Обработка текстовой команды /start
@bot.message_handler(commands=['start'])
def start_bot(message):
    open_main_menu(message)

# Обработка нажатия на кнопку "Главное меню"
@bot.message_handler(func=lambda msg: msg.text == "📋 Главное меню")
def open_main_menu(message):
    bot.send_message(message.chat.id, "Главное меню:", reply_markup=show_start_menu())


### === МЕНЮ === ###
# ===== Стартовое меню =====
def show_start_menu():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("♠️♥️ Новая игра ♣️♦️", callback_data="start_new_game"))
    keyboard.add(types.InlineKeyboardButton("🏆👥 Стат-ка игроков", callback_data="players_stat"))
    keyboard.add(types.InlineKeyboardButton("📊🃏 Стат-ка последней игры", callback_data="game_stat"))
    keyboard.add(types.InlineKeyboardButton("💸 Платежи", callback_data="payments"))
    keyboard.add(types.InlineKeyboardButton("➕👤 Создать игрока", callback_data="create_player"))
    return keyboard


# ===== Меню после старта новой игры =====
def show_game_menu():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("➕ Добавить игрока в игру", callback_data="add_player"))
    keyboard.add(types.InlineKeyboardButton("⚡ Действия с игроками", callback_data="add_action"))
    keyboard.add(types.InlineKeyboardButton("📊 Статистика игры", callback_data="game_stat"))
    keyboard.add(types.InlineKeyboardButton("🏁 Завершить игру", callback_data="close_game"))
    return keyboard


# ===== Динамическое меню выбора игроков для добавления в игру =====
def show_add_player_menu(chat_id, message_id=None):
    players = get_potential_players()
    if not players:
        bot.send_message(chat_id, "⚠️ Нет доступных игроков для добавления.")
        return
    keyboard = types.InlineKeyboardMarkup()
    row = []
    for i, p in enumerate(players, start=1):
        row.append(types.InlineKeyboardButton(p['name'], callback_data=f"add_player_{p['id']}"))
        if i % 3 == 0:   # каждые 3 кнопки — новая строка
            keyboard.row(*row)
            row = []
    if row:  # если остались не добавленные кнопки
        keyboard.row(*row)
    back_btn = types.InlineKeyboardButton("⤺ Назад", callback_data="game_menu") 
    new_player_btn = types.InlineKeyboardButton("➕👤 Создать игрока", callback_data="create_player")
    keyboard.row(back_btn, new_player_btn) #последняя строка
    text = "Выберите игрока для добавления:"
    if message_id: # если меню уже есть — обновляем его
        bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=keyboard)
    else: # если меню открывается впервые
        bot.send_message(chat_id, text, reply_markup=keyboard)


# ===== Динамическое меню действий для активных игроков =====
def show_actions_menu(chat_id):
    players = get_active_players()
    if not players:
        bot.send_message(chat_id, "⚠️ Нет активных игроков.", reply_markup=show_game_menu())
        return
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    for p in players:
        buyin_btn = types.InlineKeyboardButton(f"{p['name']} — Бай-ин 💰", callback_data=f"buyin_{p['id']}")
        exit_btn = types.InlineKeyboardButton(f"{p['name']} — Выход 🏁", callback_data=f"exit_{p['id']}")
        keyboard.add(buyin_btn, exit_btn)
    keyboard.add(types.InlineKeyboardButton("⤺ Назад", callback_data="game_menu"))
    bot.send_message(chat_id, "Выберите действие для игрока:", reply_markup=keyboard)


# ===== Динамическое меню для коррекции кол-ва фишек при выходе =====
def show_fix_exit_menu(chat_id, game_id, total_in, total_out, stats):
    keyboard = types.InlineKeyboardMarkup()
    for p in stats:
        keyboard.add(types.InlineKeyboardButton(f"{p['name']} — {p['chips_out']} фишек", callback_data=f"fix_exit_{p['id']}"))
    keyboard.add(types.InlineKeyboardButton("⤺ Назад", callback_data="game_menu"))
    text = (
        "❌ Несовпадение количества фишек!\n"
        f"Вход:    {total_in}\n"
        f"Выход: {total_out}\n\n"
        "Выберите игрока для исправления:"
    )
    bot.send_message(chat_id, text, reply_markup=keyboard)


# ===== Динамическое меню выбора года для статистики игроков =====
def show_players_years_menu(chat_id):
    current_year = datetime.datetime.now().year
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton("📅 Все годы", callback_data="players_stat_all"))
    for y in range(2025, current_year + 1):
        keyboard.add(types.InlineKeyboardButton(f"{y}", callback_data=f"players_stat_{y}"))
    keyboard.add(types.InlineKeyboardButton("⤺ Назад", callback_data="main_menu"))
    bot.send_message(chat_id, "Выберите год:", reply_markup=keyboard)


# ===== Динамическое меню обработки платежей =====
def show_payments_menu(chat_id):
    players = get_all_players()
    balances = [p for p in players if p['balance'] != 0]
    if not balances:
        text = "💸 Все балансы равны 0 ✅\n"
    else:
        text = "💸 Балансы игроков:\n\n"
        text += f"{'Игрок':<12} {'Баланс':>6}\n"
        text += "─" * 20 + "\n"
        for p in balances:
            emoji = "🟢" if p['balance'] > 0 else "🔴"
            text += f"{p['name']:<12} {p['balance']:>6} {emoji}\n"
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("🖐 Ручной расчёт", callback_data="payments_manual"),
        types.InlineKeyboardButton("🤖 Авто-расчёт", callback_data="payments_auto"))
    keyboard.add(types.InlineKeyboardButton("⤺ Назад", callback_data="main_menu"))
    bot.send_message(chat_id, f"```\n{text}\n```", parse_mode="Markdown")
    bot.send_message(chat_id, "Выберите действие:", reply_markup=keyboard)



### ===== ОБРАБОТКА КНОПОК ===== ###
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    chat_id = call.message.chat.id

    # Показать главное меню
    if call.data == "main_menu":
        bot.send_message(chat_id, "Главное меню:", reply_markup=show_start_menu())

    # Старт новой игры
    elif call.data == "start_new_game":
        game_id = get_active_game()
        if not game_id:
            create_new_game()
            bot.send_message(chat_id, "🎲 Новая игра стартовала!", reply_markup=show_game_menu())
        else:
            bot.send_message(chat_id, "⚠️ Уже есть активная игра.", reply_markup=show_game_menu())

    # Показать игровое меню
    elif call.data == "game_menu":
        bot.send_message(chat_id, "Основное меню игры:", reply_markup=show_game_menu())

    # Показать меню добавления игрока в игру
    elif call.data == "add_player":
        show_add_player_menu(chat_id, call.message.message_id)

    # Показать меню действий для игрока: бай-ин или выход
    elif call.data == "add_action":
        show_actions_menu(chat_id)

    # Добавление конкретного игрока в игру
    elif call.data.startswith("add_player_"):
        player_id = call.data.split("_")[2]
        player = get_player(player_id)
        if player["is_playing"] != 1:
            add_player(get_active_game(), player_id)
            bot.send_message(chat_id, f"✅ Игрок {player['name']} добавлен в игру.")
            # После добавления — обновляем список доступных игроков
            show_add_player_menu(call.message.chat.id, call.message.message_id)
        else:
            bot.send_message(chat_id, f"️⚠️ Игрок {player['name']} уже участвует в игре.")

    # Бай-ин конкретного игрока
    elif call.data.startswith("buyin_"):
        player_id = call.data.split("_")[1]
        add_buyin(get_active_game(), player_id)
        bot.send_message(chat_id, f"💰 Бай-ин учтён для игрока {get_player(player_id)['name']}.")

    # Выход конкретного игрока
    elif call.data.startswith("exit_"):
        player_id = call.data.split("_")[1]
        msg = bot.send_message(chat_id, f"Введите число фишек, которые выиграл игрок {get_player(player_id)['name']}:")
        bot.register_next_step_handler(msg, process_exit, player_id)

    # Исправление числа фишек при выходе
    elif call.data.startswith("fix_exit_"):
        player_id = call.data.split("_")[2]
        msg = bot.send_message(chat_id, f"Введите исправленное число фишек для игрока {get_player(player_id)['name']}:")
        bot.register_next_step_handler(msg, process_fix_exit, player_id)

    # Завершение текущей игры
    elif call.data == "close_game":
        game_id = get_active_game()
        if not game_id:
            bot.send_message(chat_id, "⚠️ Нет активной игры.", reply_markup=show_start_menu())
            return
        players = get_active_players()
        if players:
            bot.send_message(chat_id, "⚠️ В текущей игре есть активные игроки.")
            show_actions_menu(chat_id)
            return
        total_in, total_out, stats = validate_game_balance(game_id)
        if total_in != total_out:
            show_fix_exit_menu(chat_id, game_id, total_in, total_out, stats)
            return
        close_game(game_id)
        bot.send_message(chat_id, "🏁 Текущая игра завершена.", reply_markup=show_start_menu())

    # Создание нового игрока
    elif call.data == "create_player":
        msg = bot.send_message(chat_id, "Введите имя нового игрока:")
        bot.register_next_step_handler(msg, create_new_player)



    # Статистика текущей или последней игры
    elif call.data == "game_stat":
        active_game = True
        game_id = get_active_game()
        if not game_id:
            #bot.send_message(chat_id, "⚠️ Нет активной игры. Статистика последней игры:")
            game_id = get_last_game()
            active_game = False
        game_date = get_game_date(game_id)
        players = get_game_stat(game_id)
        if not players:
            bot.send_message(chat_id, "⚠️ Список игроков пуст.")
            return

        total_players = len(players)
        active_players = sum(1 for p in players if p["is_playing"])
        total_bank = 0
        worst_result = min(p['money_out'] - p['money_in'] for p in players)
        text = f"🃏📊 Статистика игры от {game_date}:\n\n"
        if active_game:
            players_col_title = f"Игрок ({active_players}/{total_players})"
        else:
            players_col_title = f"Игрок ({total_players})"
        text += f"{players_col_title:<12} {'🛒':>2} {'🔘out':>5} {'Итог💰':>8}\n"
        text += "─" * 30 + "\n"

        for idx, p in enumerate(players):
            result = p['money_out']-p['money_in']
            if active_game:# Активная игра → иконка только для вышедшего игрока
                status_icon = "🏁" if not p["is_playing"] else "  "
            else:# Завершённая игра
                status_icon = "  "
                if idx < 3: status_icon = ["🥇", "🥈", "🥉"][idx]
                if result == worst_result: status_icon = "🐟"
                if result == 0: status_icon = "💎"
                if idx == 0 and p['name'] == "Роман": status_icon = "🎼"
                if idx == 0 and p['name'] == "Илья Т": status_icon = "🍾"
                if idx == 0 and p['name'] == "Виктор С": status_icon = "🗽"
                if result == worst_result and p['name'] == "Виктор В": status_icon = "🐋"
            text += f"{status_icon} {p['name']:<10} {p['buyins']:<2} {p['chips_out']:>6} {result:>8}\n"
            total_bank += p['money_in']

        text += "\n" + "Общий банк: " + str(total_bank) + " " + CURRENCY 
        bot.send_message(chat_id, f"```\n{text}\n```", parse_mode="Markdown")

    # Вывод статистики игроков -> выбор года
    elif call.data == "players_stat":
        show_players_years_menu(chat_id)

    # Статистика игроков за конкретный год
    elif call.data.startswith("players_stat_"):
        year_part = call.data.split("_")[-1]
        year = None if year_part == "all" else int(year_part)
        players = get_players_stat(year)
        if not players:
            bot.send_message(chat_id, "⚠️ Список игроков пуст.")
            return
        text = f"👥📈 Статистика игроков за {year if year else 'все годы'}:\n\n"
        text += f"{'Игрок':<10}{'Игр':<4}{'Траты':<6}{'Выигрыш':>7}{'Баланс':>7}\n"
        text += "─" * 30 + "\n"  # разделитель
        for p in players:
            text += f"{p['name']:<10}{p['games_count']:>2}{p['spent']:>7}{p['earned']:>7}{p['balance']:>7}\n"
        bot.send_message(chat_id, f"```\n{text}\n```", parse_mode="Markdown")



    # Показать меню платежей
    elif call.data == "payments":
        show_payments_menu(chat_id)

    # Выбор отправителя для ручного платежа
    elif call.data == "payments_manual":
        players = get_all_players()
        debtors = [p for p in players if p['balance'] < 0]
        if not debtors:
            bot.send_message(chat_id, "✅ Должников нет")
            return
        keyboard = types.InlineKeyboardMarkup()
        for p in debtors:
            keyboard.add(types.InlineKeyboardButton(f"{p['name']} ({abs(p['balance'])})", callback_data=f"payment_from_{p['id']}"))
        keyboard.add(types.InlineKeyboardButton("⤺ Назад", callback_data="payments"))
        bot.send_message(chat_id, "Выберите должника:", reply_markup=keyboard)

    # Выбор получателя для ручного платежа
    elif call.data.startswith("payment_from_"):
        debtor_id = call.data.split("_")[2]
        players = get_all_players()
        creditors = [p for p in players if p['balance'] != 0 and p['id'] != debtor_id] 
        #можно доработать логику: выводить только игроков из последней игры
        if not creditors:
            bot.send_message(chat_id, "✅ Кредиторов нет.")
            return
        keyboard = types.InlineKeyboardMarkup()
        for p in creditors:
            keyboard.add(types.InlineKeyboardButton(f"{p['name']} ({p['balance']})", callback_data=f"payment_to_{p['id']}_from_{debtor_id}"))
        keyboard.add(types.InlineKeyboardButton("⤺ Назад", callback_data="payments_manual"))
        bot.send_message(chat_id, "Выберите кому платить:", reply_markup=keyboard)

    # Определение суммы ручного платежа
    elif call.data.startswith("payment_to_"):
        debtor_id = int(call.data.split("_")[4])
        creditor_id = int(call.data.split("_")[2])
        debtor = get_player(debtor_id)
        creditor = get_player(creditor_id)
        if -debtor['balance'] <= creditor['balance']: #дебитор переводит кредитору весь свой долг
            amount = -debtor['balance']
            execute_payment(debtor_id, creditor_id, amount)
            bot.send_message(chat_id, f"✅ {debtor['name']} перевел {creditor['name']}: {amount} {CURRENCY}")
            show_payments_menu(chat_id)
        else: #если дебитор должен больше, чем кредитор имеет, то нужно выбрать сумму перевода
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            if creditor['balance'] <= 0:
                keyboard.add(types.InlineKeyboardButton(f"{-debtor['balance']} {CURRENCY}", callback_data=f"execute_payment_{debtor['id']}_{creditor['id']}_{-debtor['balance']}"),
                            types.InlineKeyboardButton(f"{creditor['balance']} {CURRENCY}", callback_data=f"execute_payment_{debtor['id']}_{creditor['id']}_{creditor['balance']}"))
            else:                
                keyboard.add(types.InlineKeyboardButton(f"{-debtor['balance']} {CURRENCY}", callback_data=f"execute_payment_{debtor['id']}_{creditor['id']}_{-debtor['balance']}"))
            keyboard.add(types.InlineKeyboardButton("✏️ Ввести вручную", callback_data=f"execute_payment_{debtor['id']}_{creditor['id']}_{debtor['balance']}"),
                         types.InlineKeyboardButton("⤺ Назад", callback_data="payments_manual"))
            bot.send_message(chat_id, f"Выберите сумму перевода от {debtor['name']} к {creditor['name']}:", reply_markup=keyboard)

    # Автоматический расчёт платежей
    elif call.data == "payments_auto":
        payments = calculate_payments()
        if not payments:
            bot.send_message(chat_id, "✅ Все расчёты закрыты, долгов нет.")
            return
        text = "💸 Расчёт долгов:\n\n"
        keyboard = types.InlineKeyboardMarkup()
        for p in payments:
            keyboard.add(types.InlineKeyboardButton(f"{p['from_name']} → {p['to_name']} {p['amount']} {CURRENCY}",
                    callback_data=f"execute_payment_{p['from_id']}_{p['to_id']}_{p['amount']}"))
        bot.send_message(chat_id, text, reply_markup=keyboard)

    # Проведение платежа (от кого, кому, сумма)
    elif call.data.startswith("execute_payment_"):
        _,_, from_id, to_id, amount = call.data.split("_")
        from_id, to_id, amount = int(from_id), int(to_id), int(amount)
        if amount > 0:
            execute_payment(from_id, to_id, amount)
            bot.send_message(chat_id, f"✅ {get_player(from_id)['name']} перевел {get_player(to_id)['name']}: {amount} {CURRENCY}")
            show_payments_menu(chat_id)
        else:
            msg = bot.send_message(chat_id, f"Введите сумму перевода от {get_player(from_id)['name']} к {get_player(to_id)['name']}:")
            bot.register_next_step_handler(msg, process_manual_payment, from_id, to_id, -amount)	



# === ЛОГИКА ДЕЙСТВИЙ ===
def create_new_player(message):
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "⚠️ Имя не может быть пустым.")
        return
    existing_players = [p['name'].lower() for p in get_all_players()]
    if name.lower() in existing_players: # Проверяем, существует ли игрок с таким именем
        bot.send_message(message.chat.id, f"⚠️ Игрок с именем {name} уже существует.", reply_markup=show_start_menu())
        return
    create_player(name)
    bot.send_message(message.chat.id, f"✅ Игрок {name} успешно добавлен!")


def process_exit(message, player_id):
    try:
        chips = int(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ Введите корректное число фишек:")
        return bot.register_next_step_handler(message, process_exit, player_id)
    if chips < 0:
        bot.send_message(message.chat.id, "⚠️ Число фишек не может быть отрицательным. Введите корректное число фишек:")
        return bot.register_next_step_handler(message, process_exit, player_id)
    exit_player(get_active_game(), player_id, chips)
    bot.send_message(message.chat.id, f"🏁 Игрок {get_player(player_id)['name']} закончил игру с {chips} фишками.")
    show_actions_menu(message.chat.id)


def process_fix_exit(message, player_id):
    try:
        chips = int(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ Введите корректное число фишек:")
        return bot.register_next_step_handler(message, process_fix_exit, player_id)
    if chips < 0:
        bot.send_message(message.chat.id, "⚠️ Число фишек не может быть отрицательным. Введите корректное число фишек:")
        return bot.register_next_step_handler(message, process_fix_exit, player_id)
    game_id = get_active_game()
    update_exit_chips(game_id, player_id, chips)
    total_in, total_out, stats = validate_game_balance(game_id)
    if total_in == total_out:
        close_game(game_id)
        bot.send_message(message.chat.id, "✅ Ошибка исправлена. Игра закрыта!")
    else:
        show_fix_exit_menu(message.chat.id, game_id, total_in, total_out, stats)

def process_manual_payment(message, debtor_id, creditor_id, max_transfer):
    try:
        amount = int(message.text)
    except ValueError:
        msg = bot.send_message(message.chat.id, "⚠️ Введите корректное число:")
        return bot.register_next_step_handler(msg, process_manual_payment, debtor_id, creditor_id, max_transfer)
    if amount <= 0 or amount > max_transfer:
        msg = bot.send_message(message.chat.id, f"⚠️ Неверная сумма. Введите число от 1 до {max_transfer}")
        return bot.register_next_step_handler(msg, process_manual_payment, debtor_id, creditor_id, max_transfer)
    execute_payment(debtor_id, creditor_id, amount)
    bot.send_message(message.chat.id, f"✅ {get_player(debtor_id)['name']} перевел {get_player(creditor_id)['name']}: {amount} {CURRENCY}")
    show_payments_menu(message.chat.id)



# === ЗАПУСК БОТА===
if __name__ == "__main__":
    print("✅ Бот запущен...")
    bot.polling(none_stop=True)
