import sqlite3
import os
import logging

_connection = None

logger = logging.getLogger(__name__)


def get_db_connection(db_path="data/database.db"):
    global _connection
    if _connection is None:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        _connection = sqlite3.connect(db_path, check_same_thread=False)
        _connection.row_factory = sqlite3.Row
    return _connection


def close_db_connection():
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


def init_db(topic_names: dict | None = None, group_settings: dict | None = None):
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
            spiski BOOLEAN NOT NULL DEFAULT 1,
            directions NOT NULL DEFAULT 0
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY
        )
    """)

    if topic_names:
        cursor.execute("PRAGMA table_info(subscriptions)")
        existing = {row[1] for row in cursor.fetchall()}
        for topic in topic_names:
            if topic not in existing:
                logger.info(f"Adding column '{topic}' to subscriptions table")
                cursor.execute(
                    f"ALTER TABLE subscriptions ADD COLUMN {topic} INTEGER NOT NULL DEFAULT 1"
                )

    if group_settings:
        cursor.execute("PRAGMA table_info(groups)")
        existing = {row[1] for row in cursor.fetchall()}
        for setting in group_settings:
            if setting not in existing:
                logger.info(f"Adding column '{setting}' to groups table")
                cursor.execute(
                    f"ALTER TABLE groups ADD COLUMN {setting} INTEGER NOT NULL DEFAULT 1"
                )

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
    allowed_topics = ['new_removed_shifts', 'dates', 'polozhenie', 'dopusheni', 'mesta_provedeniya', 'spiski', "directions"]
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
    cursor.execute("INSERT OR IGNORE INTO subscriptions (id) VALUES (?)", (group_id,))
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


def get_group_settings(group_id: int):
    """Returns the entire settings row for a group, or None."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM groups WHERE group_id = ?", (group_id,))
    return cursor.fetchone()


def toggle_group_setting(group_id: int, setting: str) -> bool | None:
    """Toggles a boolean setting for a group. Returns the new value, or None on error."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM groups WHERE group_id = ?", (group_id,))
    row = cursor.fetchone()
    if row is None:
        return None
    try:
        current = row[setting]
    except (IndexError, KeyError):
        return None
    new_value = 0 if current else 1
    cursor.execute(
        f"UPDATE groups SET {setting} = ? WHERE group_id = ?",
        (new_value, group_id),
    )
    conn.commit()
    return bool(new_value)
