import sqlite3
import logging
import config
from datetime import datetime

logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.db_path = config.DB_PATH
        self.connection = None
        self.connect()
        self.create_tables()

    def connect(self):
        """Подключение к SQLite базе данных"""
        try:
            self.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row  # Для получения результатов как словарей
            logger.info(f"Successfully connected to SQLite database: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Error connecting to SQLite: {e}")
            self.connection = None

    def create_tables(self):
        """Создание таблиц в базе данных"""
        if not self.connection:
            logger.error("No database connection")
            return
            
        try:
            cursor = self.connection.cursor()
            
            # Таблица пользователей с доступом
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS allowed_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER UNIQUE NOT NULL,
                    username TEXT,
                    first_name TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            self.connection.commit()
            cursor.close()
            logger.info("Database tables created successfully")
            
            # Добавляем админа автоматически
            self.add_user(config.ADMIN_ID, "admin", "Admin")
            
        except sqlite3.Error as e:
            logger.error(f"Error creating tables: {e}")

    def add_user(self, user_id, username=None, first_name=None):
        """Добавить пользователя в список разрешенных или обновить его данные"""
        if not self.connection:
            return False
            
        try:
            cursor = self.connection.cursor()
            # Используем INSERT OR REPLACE для обновления данных если пользователь уже есть
            cursor.execute("""
                INSERT INTO allowed_users (user_id, username, first_name) 
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name
            """, (user_id, username, first_name))
            self.connection.commit()
            cursor.close()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error adding user: {e}")
            return False

    def remove_user(self, user_id):
        """Удалить пользователя из списка разрешенных"""
        if not self.connection:
            return False
            
        try:
            cursor = self.connection.cursor()
            cursor.execute("DELETE FROM allowed_users WHERE user_id = ?", (user_id,))
            self.connection.commit()
            cursor.close()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error removing user: {e}")
            return False

    def is_user_allowed(self, user_id):
        """Проверить есть ли у пользователя доступ"""
        if not self.connection:
            return False
            
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT user_id FROM allowed_users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            cursor.close()
            return result is not None
        except sqlite3.Error as e:
            logger.error(f"Error checking user access: {e}")
            return False

    def get_all_users(self):
        """Получить список всех пользователей с доступом"""
        if not self.connection:
            return []
            
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT * FROM allowed_users ORDER BY added_at DESC")
            rows = cursor.fetchall()
            cursor.close()
            
            # Конвертируем Row объекты в словари
            users = []
            for row in rows:
                users.append({
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'username': row['username'],
                    'first_name': row['first_name'],
                    'added_at': row['added_at']
                })
            return users
        except sqlite3.Error as e:
            logger.error(f"Error getting users: {e}")
            return []

    def get_user_by_username(self, username):
        """Найти пользователя по username"""
        if not self.connection:
            return None
            
        try:
            cursor = self.connection.cursor()
            cursor.execute("SELECT * FROM allowed_users WHERE username = ?", (username,))
            row = cursor.fetchone()
            cursor.close()
            
            if row:
                return {
                    'id': row['id'],
                    'user_id': row['user_id'],
                    'username': row['username'],
                    'first_name': row['first_name'],
                    'added_at': row['added_at']
                }
            return None
        except sqlite3.Error as e:
            logger.error(f"Error finding user by username: {e}")
            return None

    def close(self):
        """Закрыть соединение с базой данных"""
        if self.connection:
            self.connection.close()
            logger.info("SQLite connection closed")
