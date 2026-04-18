import sqlite3
import os
from datetime import datetime
import uuid

DB_PATH = "../db/finally.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users_profile (
        id TEXT PRIMARY KEY,
        cash_balance REAL DEFAULT 10000.0,
        created_at TEXT
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS watchlist (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        ticker TEXT,
        added_at TEXT,
        UNIQUE(user_id, ticker)
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS positions (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        ticker TEXT,
        quantity REAL,
        avg_cost REAL,
        updated_at TEXT,
        UNIQUE(user_id, ticker)
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS trades (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        ticker TEXT,
        side TEXT,
        quantity REAL,
        price REAL,
        executed_at TEXT
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        total_value REAL,
        recorded_at TEXT
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_messages (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        role TEXT,
        content TEXT,
        actions TEXT,
        created_at TEXT
    )''')

    # Seed default user
    cursor.execute("INSERT OR IGNORE INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
                   ("default", 10000.0, datetime.now().isoformat()))

    # Seed default watchlist
    default_tickers = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]
    for ticker in default_tickers:
        cursor.execute("INSERT OR IGNORE INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
                       (str(uuid.uuid4()), "default", ticker, datetime.now().isoformat()))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully.")
