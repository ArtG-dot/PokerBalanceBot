import os

# Telegram Token
TOKEN = os.environ.get("POKER_BOT_TOKEN")

# Название базы
DB_NAME = "poker.db"

# Настройки игры
BUYIN_VALUE = 100      # Стоимость одного байина (в кронах)
CHIPS_PER_BUYIN = 500    # Кол-во фишек за байин
CHIPS_PER_CURRENCY = 5 # Кол-во фишек за 1 крону
CURRENCY = "CZK"         # Валюта для вывода

# Игроки
PLAYERS = [
]
