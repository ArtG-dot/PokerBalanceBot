from os import error
import sqlite3
from config import DB_NAME, BUYIN_VALUE, CHIPS_PER_BUYIN, CHIPS_PER_CURRENCY, CURRENCY
from datetime import datetime
from db import connect


# Логика работы с игроками
def create_player(name):
    with connect() as conn:
        conn.execute("INSERT INTO players (name) VALUES (?)", (name,))

def get_all_players():
    with connect() as conn:
        return conn.execute("SELECT id, name, spent, earned, balance FROM players ORDER BY id").fetchall()

def get_active_players():
    with connect() as conn:
        return conn.execute("SELECT id, name FROM players WHERE is_playing=1 ORDER BY id").fetchall()

def get_potential_players():
    with connect() as conn: #sorting by count of games
        return conn.execute("""SELECT p.id, p.name FROM players p LEFT JOIN activities a ON p.id = a.player_id
            WHERE is_playing=0 AND a.action='add' GROUP BY p.id, p.name ORDER BY COUNT(a.id) DESC, p.id""").fetchall()
        
def get_game_players(game_id):
    with connect() as conn:
        return conn.execute("SELECT id, name, is_playing FROM players WHERE last_game_id=? ORDER BY id", (game_id,)).fetchall()

def get_player_name(player_id):
    with connect() as conn:
        name = conn.execute("SELECT name FROM players WHERE id=?", (player_id,)).fetchone()
        return name[0] if name else None

def check_player_active(player_id):
    with connect() as conn:
        is_playing = conn.execute("SELECT is_playing FROM players WHERE id=?", (player_id,)).fetchone()
        return is_playing[0] if is_playing else None



## Логика работы с играми
def create_new_game():
    with connect() as conn:
        conn.execute("INSERT INTO games (start_time) VALUES (?)", (datetime.now().strftime('%Y-%m-%d'),))

def get_active_game():
    with connect() as conn:
        row = conn.execute("SELECT id FROM games WHERE is_active=1").fetchone()
        return row[0] if row else None

def get_last_game():
    with connect() as conn:
        row = conn.execute("SELECT id FROM games ORDER BY id DESC LIMIT 1").fetchone()
        return row[0] if row else None

def get_game_date(game_id):
    with connect() as conn:
        row = conn.execute("SELECT start_time FROM games WHERE id=?", (game_id,)).fetchone()
        return row[0] if row else None

def close_game(game_id):
    with connect() as conn:
        conn.execute("UPDATE games SET is_active=0, end_time=? WHERE id=?", (datetime.now().strftime('%Y-%m-%d'), game_id))
        conn.commit()

def validate_game_balance(game_id):
    stats = get_game_stat(game_id)
    total_in = sum(p["chips_in"] for p in stats)
    total_out = sum(p["chips_out"] for p in stats)
    return total_in, total_out, stats

def update_exit_chips(game_id, player_id, new_amount):
    with connect() as conn:
        conn.execute("UPDATE activities SET chips_amount=? WHERE game_id=? AND player_id=? AND action='exit'", (new_amount, game_id, player_id))
        conn.commit()


#Логика работы со статистикой
def get_players_stat(year=None):
    with connect() as conn:
        query = """SELECT p.id, p.name,
                   COALESCE(SUM(IIF(a.action='buyin', ?, 0)), 0) spent,
                   COALESCE(SUM(IIF(a.action='exit', a.chips_amount/?, 0)), 0) earned,
                   COALESCE(SUM(IIF(a.action='exit', a.chips_amount/?, 0)) - SUM(IIF(a.action='buyin', ?, 0)),0) balance,
                   COUNT(DISTINCT g.id) games_count
            FROM players p
            LEFT JOIN activities a ON p.id = a.player_id
            LEFT JOIN games g ON a.game_id = g.id
            WHERE 1=1"""
        params = [BUYIN_VALUE, CHIPS_PER_CURRENCY, CHIPS_PER_CURRENCY, BUYIN_VALUE]
        if year:
            query += " AND strftime('%Y', g.start_time)=?"
            params.append(str(year))
        query += " GROUP BY p.id, p.name ORDER BY p.id"
        rows = conn.execute(query, params).fetchall()
    stats = []
    for r in rows:
        stats.append({
            "id": r[0],
            "name": r[1],
            "spent": r[2],
            "earned": r[3],
            "balance": r[4],
            "games_count": r[5]
        })
    return stats

def get_game_stat(game_id):
    with connect() as conn:
        rows = conn.execute("""SELECT p.id, p.name, p.is_playing
            , SUM(IIF(a.action='buyin', 1, 0)) buyins
            , SUM(IIF(a.action='buyin', 1, 0))*? chips_in
            , SUM(IIF(a.action='exit', a.chips_amount, 0)) chips_out
            , CAST(SUM(IIF(a.action='buyin', 1, 0))*? AS INT) money_in
            , CAST(SUM(IIF(a.action='exit', a.chips_amount, 0))/? AS INT) money_out
            FROM players p
            INNER JOIN activities a ON p.id = a.player_id
            WHERE a.game_id = ?
            GROUP BY p.id, p.name, p.is_playing
            ORDER BY (money_out - money_in) DESC""",(CHIPS_PER_BUYIN, BUYIN_VALUE, CHIPS_PER_CURRENCY, game_id)).fetchall()
        stats = []
        for r in rows:
            stats.append({
                "id": r[0],
                "name": r[1],
                "is_playing": r[2],
                "buyins": r[3],
                "chips_in": r[4],
                "chips_out": r[5],
                "money_in": r[6],
                "money_out": r[7]
            })
        return stats



#Логика работы с активностями
def add_player(game_id, player_id):
    with connect() as conn:
        conn.execute("INSERT INTO activities (game_id, player_id, action) VALUES (?, ?, ?)", (game_id, player_id, "add"))
        conn.execute("UPDATE players SET is_playing=1, last_game_id=? WHERE id=?", (game_id, player_id))
        conn.commit()
    add_buyin(game_id, player_id)

def add_buyin(game_id, player_id):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("INSERT INTO activities (game_id, player_id, action, chips_amount) VALUES (?, ?, ?, ?)", (game_id, player_id, "buyin", CHIPS_PER_BUYIN))
        conn.execute("UPDATE players SET spent=spent+?, balance=balance-? WHERE id=?", (BUYIN_VALUE, BUYIN_VALUE, player_id))
        conn.commit()

def exit_player(game_id, player_id, chips):
    with sqlite3.connect(DB_NAME) as conn:
        conn.execute("INSERT INTO activities (game_id, player_id, action, chips_amount) VALUES (?, ?, ?, ?)", (game_id, player_id, "exit", chips))
        conn.execute("UPDATE players SET is_playing=0, earned=earned+?/?, balance=balance+?/?  WHERE id=?", (chips, CHIPS_PER_CURRENCY, chips, CHIPS_PER_CURRENCY, player_id))
        conn.commit()



#Логика работы с платежами
def calculate_payments():
    players = get_all_players()

    # Составляем словарь балансов: id → (name, balance)
    balances = {p[0]: {"name": p[1], "balance": p[4]} for p in players}
    # Списки должников и кредиторов
    debtors = [(pid, info["name"], -info["balance"]) for pid, info in balances.items() if info["balance"] < 0]
    creditors = [(pid, info["name"], info["balance"]) for pid, info in balances.items() if info["balance"] > 0]

    # Сортируем по величине долга/кредита (крупные сначала)
    debtors.sort(key=lambda x: x[2], reverse=True)
    creditors.sort(key=lambda x: x[2], reverse=True)

    payments = []
    i, j = 0, 0

    while i < len(debtors) and j < len(creditors):
        debtor_id, debtor_name, debt_amount = debtors[i]
        creditor_id, creditor_name, credit_amount = creditors[j]

        # Сумма перевода — минимальная из оставшегося долга и кредита
        amount = min(debt_amount, credit_amount)
        payments.append({
            "from_id": debtor_id,
            "from_name": debtor_name,
            "to_id": creditor_id,
            "to_name": creditor_name,
            "amount": int(amount)
        })

        # Обновляем долги и кредиты
        debt_amount -= amount
        credit_amount -= amount

        # Если долг погашен — переходим к следующему должнику
        if debt_amount == 0:
            i += 1
        else:
            debtors[i] = (debtor_id, debtor_name, debt_amount)

        # Если кредит погашен — переходим к следующему кредитору
        if credit_amount == 0:
            j += 1
        else:
            creditors[j] = (creditor_id, creditor_name, credit_amount)

    return payments

def record_payment(from_id, to_id, amount, user="system"):
    with connect() as conn:
        conn.execute("""
            INSERT INTO payments (timestamp, from_player_id, to_player_id, money_amount, user)
            VALUES (?, ?, ?, ?, ?)""",
            (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), from_id, to_id, amount, user))
        conn.commit()

def apply_payment(from_id, to_id, amount):
    with connect() as conn:
        conn.execute("UPDATE players SET balance = balance + ? WHERE id=?", (amount, from_id))
        conn.execute("UPDATE players SET balance = balance - ? WHERE id=?", (amount, to_id))
        conn.commit()
