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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY
        )
    """)
    conn.commit()


def add_user(id, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (id, username))
    cursor.execute("INSERT OR IGNORE INTO subscriptions (id) VALUES (?)", (id,))
    conn.commit()


def check_username(id, username):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET username = ? WHERE id = ? AND username IS NOT ?", (username, id, username))
    conn.commit()

def update_user_name(user_id, name, surname):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET name = ?, surname = ? WHERE id = ?",
        (name, surname, user_id),
    )
    conn.commit()

def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    return cursor.fetchall()

def get_user_by_id(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    return cursor.fetchone()


def get_user_by_name(name, surname):
    """
    Возвращает пользователя по имени и фамилии.
    Учитывает, что вместо 'е' может быть 'ё' и наоборот, и не зависит от регистра.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM users
        WHERE replace(lower(name), 'ё', 'е') = replace(lower(?), 'ё', 'е')
          AND replace(lower(surname), 'ё', 'е') = replace(lower(?), 'ё', 'е')
    """, (name, surname))
    user = cursor.fetchone()
    return user


def get_user_by_surname(surname):
    """
    Возвращает пользователя по фамилии.
    Учитывает, что вместо 'е' может быть 'ё' и наоборот, и не зависит от регистра.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM users
        WHERE replace(lower(surname), 'ё', 'е') = replace(lower(?), 'ё', 'е')
    """, (surname,))
    user = cursor.fetchone()
    return user


def get_subscribers_by_topic(topic: str):
    """
    Возвращает данные о всех пользователях, для которых указанная тема рассылки активна.
    """
    allowed_topics = ['new_removed_shifts', 'dates', 'polozhenie', 'dopusheni', 'mesta_provedeniya', 'spiski']
    if topic not in allowed_topics:
        return []

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT id FROM subscriptions WHERE {topic} = 1")
    users = cursor.fetchall()
    return users


def get_subscription_status(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM subscriptions WHERE id = ?", (user_id,))
    return cursor.fetchone()

def update_subscription(user_id, topic, status):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"UPDATE subscriptions SET {topic} = ? WHERE id = ?", (status, user_id))
    conn.commit()

def add_group(group_id):
    """Adds a group to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO groups (group_id) VALUES (?)", (group_id,))
    conn.commit()

def remove_group(group_id):
    """Removes a group from the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM groups WHERE group_id = ?", (group_id,))
    conn.commit()

def get_all_groups():
    """Returns a list of all group IDs."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT group_id FROM groups")
    groups = cursor.fetchall()
    return [group['group_id'] for group in groups]
