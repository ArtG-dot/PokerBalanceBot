import sqlite3
from config import DB_NAME, PLAYERS

def connect():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = connect()
    c = conn.cursor()
    # Таблица игр
    c.execute('''
    CREATE TABLE IF NOT EXISTS games (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        start_time TEXT,
        end_time TEXT,
        is_active INTEGER DEFAULT 1)
    ''')

    # Таблица игроков
    c.execute('''
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        is_playing INTEGER DEFAULT 0,
        spent INTEGER DEFAULT 0,
        earned INTEGER DEFAULT 0,
        balance INTEGER DEFAULT 0,
        last_game_id INTEGER)
    ''')

    # Добавить игроков из конфига
    for player in PLAYERS:
        c.execute("INSERT OR IGNORE INTO players (name) VALUES (?)", (player,))

    # Таблица активности (игра)
    c.execute('''
    CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        game_id INTEGER,
        player_id INTEGER,
        action TEXT,
        chips_amount INTEGER,
        user TEXT)
    ''')

    # Таблица платежей
    c.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        from_player_id INTEGER,
        to_player_id INTEGER,
        money_amount INTEGER,
        user TEXT)
    ''')


    rows = c.execute("SELECT id, name, balance FROM players").fetchall()
    print("\n=== Список игроков ===")
    for r in rows:
        print(r)
    print("=======================\n")

    
    conn.commit()
    conn.close()
