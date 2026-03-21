import sqlite3
import os

_connection = None


def get_db_connection(db_path="data/database.db"):
    global _connection
    if _connection is None:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        _connection = sqlite3.connect(db_path)
        _connection.row_factory = sqlite3.Row
    return _connection


def close_db_connection():
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT,
            surname TEXT,
            username TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY,
            new_removed_shifts BOOLEAN NOT NULL DEFAULT 1,
            dates BOOLEAN NOT NULL DEFAULT 1,
            polozhenie BOOLEAN NOT NULL DEFAULT 1,
            dopusheni BOOLEAN NOT NULL DEFAULT 1,
            mesta_provedeniya BOOLEAN NOT NULL DEFAULT 1,
            spiski BOOLEAN NOT NULL DEFAULT 1
        )
    """)
    conn.commit()


def check_username(id, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET username = ? WHERE id = ? AND username IS NOT ?", (username, id, username))
    conn.commit()


def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    return cursor.fetchall()


def get_user_id_by_name(name, surname):
    """
    Возвращает id пользователя по имени и фамилии.
    Учитывает, что вместо 'е' может быть 'ё' и наоборот, и не зависит от регистра.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM users
        WHERE replace(lower(name), 'ё', 'е') = replace(lower(?), 'ё', 'е')
          AND replace(lower(surname), 'ё', 'е') = replace(lower(?), 'ё', 'е')
    """, (name, surname))
    user = cursor.fetchone()
    if user:
        return user['id']
    return None


def get_user_id_by_surname(surname):
    """
    Возвращает id пользователя по фамилии.
    Учитывает, что вместо 'е' может быть 'ё' и наоборот, и не зависит от регистра.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id FROM users
        WHERE replace(lower(surname), 'ё', 'е') = replace(lower(?), 'ё', 'е')
    """, (surname,))
    user = cursor.fetchone()
    if user:
        return user['id']
    return None


def get_subscribers_by_topic(topic: str):
    """
    Возвращает id всех пользователей, для которых указанная тема рассылки активна.
    """
    allowed_topics = ['new_removed_shifts', 'dates', 'polozhenie', 'dopusheni', 'mesta_provedeniya', 'spiski']
    if topic not in allowed_topics:
        return []

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT id FROM subscriptions WHERE {topic} = 1")
    users = cursor.fetchall()
    return users
