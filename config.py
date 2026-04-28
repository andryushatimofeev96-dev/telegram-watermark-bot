import os

# Токен бота - берется из переменной окружения или из файла
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8730387586:AAGhp9ZwAxXSTgW961H11bS1lzdg0mc-yM8")

# ID администратора
ADMIN_ID = int(os.environ.get("ADMIN_ID", "8320384091"))

# Папка для хранения ватермарков
WATERMARKS_DIR = os.environ.get("WATERMARKS_DIR", "watermarks")

# Папка для временных файлов
TEMP_DIR = os.environ.get("TEMP_DIR", "temp")

# База данных SQLite
DB_PATH = os.environ.get("DB_PATH", "bot_database.db")

# Настройки ватермарка
WATERMARK_OPACITY = 77
WATERMARK_SIZE_PERCENT = 0.2
WATERMARK_PADDING_X = 50
WATERMARK_PADDING_Y = 50
