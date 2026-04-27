# Конфигурация бота
# Скопируйте этот файл в config.py и заполните своими данными

# Токен бота от @BotFather
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

# ID администратора (замените на свой Telegram ID)
ADMIN_ID = 8320384091

# Папка для хранения ватермарков
WATERMARKS_DIR = "watermarks"

# Папка для временных файлов
TEMP_DIR = "temp"

# База данных SQLite (создается автоматически)
DB_PATH = "bot_database.db"

# Настройки ватермарка
WATERMARK_OPACITY = 77  # Прозрачность (0-255): 77 = 30% непрозрачности
WATERMARK_SIZE_PERCENT = 0.2  # Размер ватермарка (20% от ширины фото)
WATERMARK_PADDING_X = 50  # Горизонтальный отступ между ватермарками (в пикселях)
WATERMARK_PADDING_Y = 50  # Вертикальный отступ между ватермарками (в пикселях)
