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
            surname TEXT
        )
    """)
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
