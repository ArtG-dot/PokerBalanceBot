import telebot
from telebot import types
import datetime
from db import init_db
from logic import create_new_game, close_game, get_active_game, get_game_date, get_last_game, get_game_stat, validate_game_balance, \
    get_all_players, get_active_players, get_potential_players, get_player_name, check_player_active, get_players_stat, \
    create_player, add_player, exit_player, add_buyin, update_exit_chips, \
    calculate_payments, record_payment, apply_payment
from config import TOKEN, CURRENCY

# === Инициализация ===
bot = telebot.TeleBot(TOKEN)
init_db()


# ReplyKeyboard кнопка "Главное меню"
def main_reply_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn = types.KeyboardButton("📋 Главное меню")
    markup.add(btn)
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
    # Собираем клавиатуру
    keyboard = types.InlineKeyboardMarkup()
    row = []
    for i, p in enumerate(players, start=1):
        row.append(types.InlineKeyboardButton(p[1], callback_data=f"add_{p[0]}"))
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
        buyin_btn = types.InlineKeyboardButton(f"{p[1]} — Бай-ин 💰", callback_data=f"buyin_{p[0]}")
        exit_btn = types.InlineKeyboardButton(f"{p[1]} — Выход 🏁", callback_data=f"exit_{p[0]}")
        keyboard.add(buyin_btn, exit_btn)
    keyboard.add(types.InlineKeyboardButton("⤺ Назад", callback_data="game_menu"))
    bot.send_message(chat_id, "Выберите действие для игрока:", reply_markup=keyboard)


# ===== Динамическое меню для коррекции кол-ва фишек =====
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



### ===== ОБРАБОТКА КНОПОК ===== ###
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    chat_id = call.message.chat.id

    # Старт новой игры
    if call.data == "start_new_game":
        game_id = get_active_game()
        if not game_id:
            create_new_game()
            bot.send_message(chat_id, "🎲 Новая игра стартовала!", reply_markup=show_game_menu())
        else:
            bot.send_message(chat_id, "⚠️ Уже есть активная игра.", reply_markup=show_game_menu())

    # Завершение текущей игры
    if call.data == "close_game":
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
        text += f"{'Игрок':<10} {'Игр':>5} {'Потрачено':>10} {'Выиграно':>8} {'Баланс':>7}\n"
        text += "─" * 39 + "\n"  # разделитель
        for p in players:
            text += f"{p['name']:<10} {p['games_count']:>4} {p['spent']:>8} {p['earned']:>8} {p['balance']:>8}\n"
        bot.send_message(chat_id, f"```\n{text}\n```", parse_mode="Markdown")
    
    # Статистика текущей или последней игры
    elif call.data == "game_stat":
        game_id = get_active_game()
        if not game_id:
            bot.send_message(chat_id, "⚠️ Нет активной игры. Статистика последней игры")
            game_id = get_last_game()
        game_date = get_game_date(game_id)
        players = get_game_stat(game_id)
        if not players:
            bot.send_message(chat_id, "⚠️ Список игроков пуст.")
            return
        text = f"🃏📊 Статистика игры от {game_date}:\n\n"
        text += f"{'Игрок':<10} {'🛒':>2} {'Баланс 🔘':>12} {'Баланс 💵':>14}\n"
        text += "─" * 39 + "\n"  # разделитель
        for p in players:
            text += f"{p['name']:<10} {p['buyins']:>2} {p['chips_in']:>8} / {p['chips_out']:>4} {p['money_in']:>8} / {p['money_out']:>4}\n"
        bot.send_message(chat_id, f"```\n{text}\n```", parse_mode="Markdown")

    # Показать главное меню
    elif call.data == "main_menu":
        bot.send_message(chat_id, "Главное меню:", reply_markup=show_start_menu())

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
    elif call.data.startswith("add_"):
        player_id = call.data.split("_")[1]
        print(player_id)
        if not check_player_active(player_id):
            add_player(get_active_game(), player_id)
            bot.send_message(chat_id, f"✅ Игрок {get_player_name(player_id)} добавлен в игру")
            # После добавления — обновляем список доступных игроков
            show_add_player_menu(call.message.chat.id, call.message.message_id)
        else:
            bot.send_message(chat_id, f"️⚠️ Игрок {get_player_name(player_id)} уже участвует в игре")

    # Бай-ин конкретного игрока
    elif call.data.startswith("buyin_"):
        player_id = call.data.split("_")[1]
        add_buyin(get_active_game(), player_id)
        bot.send_message(chat_id, f"💰 Бай-ин учтён для игрока {get_player_name(player_id)}")
        #bot.answer_callback_query(call.id, f"💰 Бай-ин учтён для игрока {get_player_name(player_id)}")

    # Выход конкретного игрока
    elif call.data.startswith("exit_"):
        player_id = call.data.split("_")[1]
        msg = bot.send_message(chat_id, f"Введите число фишек, которые выиграл игрок {get_player_name(player_id)}")
        bot.register_next_step_handler(msg, process_exit, player_id)

    # Исправление числа фишек при выходе
    elif call.data.startswith("fix_exit_"):
        player_id = call.data.split("_")[2]
        msg = bot.send_message(chat_id, f"Введите исправленное число фишек для игрока {get_player_name(player_id)}:")
        bot.register_next_step_handler(msg, process_fix_exit, player_id)
    
    # Показать меню платежей
    elif call.data.startswith("payments"):
        payments = calculate_payments()
        if not payments:
            bot.send_message(chat_id, "✅ Все расчёты закрыты, долгов нет.")
            return

        text = "💸 Расчёт долгов:\n\n"
        keyboard = types.InlineKeyboardMarkup()
        for p in payments:
            text += f"{p['from_name']} → {p['to_name']}: {p['amount']} {CURRENCY}\n"
            keyboard.add(
                types.InlineKeyboardButton(
                    f"{p['from_name']} → {p['to_name']} {p['amount']} {CURRENCY}",
                    callback_data=
                    f"pay_{p['from_id']}_{p['to_id']}_{p['amount']}"))
        bot.send_message(chat_id, text, reply_markup=keyboard)

    # Оплата долга между игроками
    elif call.data.startswith("pay_"):
        _, from_id, to_id, amount = call.data.split("_")
        from_id, to_id, amount = int(from_id), int(to_id), int(amount)

        # Зафиксировать платёж
        record_payment(from_id, to_id, amount)
        apply_payment(from_id, to_id, amount)

        # Обновить список долгов
        payments = calculate_payments()
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        for p in payments:
            keyboard.add(
                types.InlineKeyboardButton(
                    f"{p['from_name']} → {p['to_name']} {p['amount']} {CURRENCY}",
                    callback_data=
                    f"pay_{p['from_id']}_{p['to_id']}_{p['amount']}"))
        if not payments:
            bot.edit_message_text("🎉 Все долги закрыты!",
                                  chat_id=chat_id,
                                  message_id=call.message.message_id)
        else:
            bot.edit_message_text("💸 Обновлённый расчёт долгов:",
                                  chat_id=chat_id,
                                  message_id=call.message.message_id,
                                  reply_markup=keyboard)



# === ЛОГИКА ДЕЙСТВИЙ ===
def create_new_player(message):
    name = message.text.strip()
    if not name:
        bot.send_message(message.chat.id, "⚠️ Имя не может быть пустым.")
        return
    # Проверяем, существует ли игрок
    existing_players = [p[1].lower() for p in get_all_players()]
    if name.lower() in existing_players:
        bot.send_message(message.chat.id, f"⚠️ Игрок с именем {name} уже существует.", reply_markup=show_start_menu())
        return
    # Создаем нового игрока
    create_player(name)
    bot.send_message(message.chat.id, f"✅ Игрок {name} успешно добавлен!", reply_markup=show_start_menu())


def process_exit(message, player_id):
    try:
        chips = int(message.text)
        exit_player(get_active_game(), player_id, chips)
        bot.send_message(message.chat.id, f"🏁 Игрок {get_player_name(player_id)} закончил игру с {chips} фишками")
        show_actions_menu(message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ Введите корректное число фишек.")

def process_fix_exit(message, player_id):
    try:
        chips = int(message.text)
    except ValueError:
        bot.send_message(message.chat.id, "⚠️ Введите корректное число.")
        return bot.register_next_step_handler(message, process_fix_exit, player_id)
    game_id = get_active_game()
    update_exit_chips(game_id, player_id, chips)
    total_in, total_out, stats = validate_game_balance(game_id)
    if total_in == total_out:
        close_game(game_id)
        bot.send_message(message.chat.id, "✅ Ошибка исправлена. Игра закрыта!")
    else:
        show_fix_exit_menu(message.chat.id, game_id, total_in, total_out, stats)

    
# === ЗАПУСК БОТА===
if __name__ == "__main__":
    print("✅ Бот запущен...")
    bot.polling(none_stop=True)
