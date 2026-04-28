import os
import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from PIL import Image
import config
from database import Database

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
WAITING_WATERMARK, WAITING_SLOT_NAME, WAITING_PHOTO, WAITING_OPACITY = range(4)
WAITING_USERNAME_TO_ADD, WAITING_USER_ID_TO_REMOVE = range(4, 6)

# Создание необходимых директорий
os.makedirs(config.WATERMARKS_DIR, exist_ok=True)
os.makedirs(config.TEMP_DIR, exist_ok=True)

# Очистка временной папки при запуске
def clean_temp_folder():
    """Очистка временной папки от старых файлов"""
    try:
        for filename in os.listdir(config.TEMP_DIR):
            file_path = os.path.join(config.TEMP_DIR, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
                logger.info(f"Removed temp file: {filename}")
    except Exception as e:
        logger.error(f"Error cleaning temp folder: {e}")

clean_temp_folder()


class WatermarkBot:
    def __init__(self):
        self.user_watermarks = {}  # {user_id: {slot_name: watermark_path}}
        self.watermark_opacity = {}  # {user_id: {slot_name: opacity}}
        self.temp_watermark = {}  # {user_id: temp_watermark_path}
        self.db = Database()  # Инициализация базы данных

    def is_admin(self, user_id):
        """Проверка является ли пользователь администратором"""
        return user_id == config.ADMIN_ID

    def check_access(self, user_id):
        """Проверка доступа пользователя к боту"""
        return self.db.is_user_allowed(user_id)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        user = update.effective_user
        user_id = user.id
        
        # Сначала сохраняем/обновляем информацию о пользователе
        self.db.add_user(user_id, user.username, user.first_name)
        
        # Потом проверяем доступ
        if not self.check_access(user_id):
            await update.message.reply_text(
                "❌ У вас нет доступа к этому боту.\n"
                "Обратитесь к администратору для получения доступа."
            )
            return
        
        admin_commands = ""
        if self.is_admin(user_id):
            admin_commands = "\n\n👑 Админ команды:\n/admin - Панель управления доступом"
        
        await update.message.reply_text(
            f"Привет, {user.first_name}! 👋\n\n"
            "Я бот для наложения водяных знаков на фотографии.\n\n"
            "Доступные команды:\n"
            "/add_watermark - Добавить новый ватермарк\n"
            "/list_watermarks - Показать сохраненные ватермарки\n"
            "/delete_watermark - Удалить ватермарк\n"
            "/apply - Наложить ватермарк на фото\n"
            "/help - Помощь"
            f"{admin_commands}"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help"""
        await update.message.reply_text(
            "📖 Инструкция по использованию:\n\n"
            "1️⃣ Добавьте ватермарк:\n"
            "   /add_watermark → отправьте фото ватермарка → введите название (например, slot1)\n\n"
            "2️⃣ Примените ватермарк:\n"
            "   /apply → выберите ватермарк → отправьте фото\n\n"
            "3️⃣ Управление:\n"
            "   /list_watermarks - посмотреть все ватермарки\n"
            "   /delete_watermark - удалить ватермарк\n\n"
            "Ватермарк автоматически масштабируется под размер фото!"
        )

    async def add_watermark_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало добавления ватермарка"""
        user_id = update.effective_user.id
        
        # Проверка доступа
        if not self.check_access(user_id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return ConversationHandler.END
        
        await update.message.reply_text(
            "📸 Отправьте фото или PNG-файл, который будет использоваться как ватермарк.\n"
            "⚠️ Для сохранения прозрачности отправляйте именно как файл (скрепка), а не как фото.\n"
            "Нажмите /cancel для отмены."
        )
        return WAITING_WATERMARK

    async def receive_watermark(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение фото ватермарка — принимает фото или PNG-файл"""
        user_id = update.effective_user.id

        temp_path = os.path.join(config.TEMP_DIR, f"temp_watermark_{user_id}.png")
        raw_path = None

        try:
            if update.message.photo:
                # Отправлено как сжатое фото
                photo = update.message.photo[-1]
                file = await context.bot.get_file(photo.file_id)
                await file.download_to_drive(temp_path)

            elif update.message.document:
                # Отправлено как файл
                doc = update.message.document
                mime = doc.mime_type or ""
                file_name = doc.file_name or ""

                logger.info(f"Document received: mime={mime}, file_name={file_name}")

                if not (mime in ("image/png", "image/jpeg", "image/jpg", "image/webp")
                        or file_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))):
                    await update.message.reply_text(
                        "❌ Поддерживаются только файлы PNG, JPG, WEBP.\n"
                        "Отправьте файл ватермарки ещё раз:"
                    )
                    return WAITING_WATERMARK

                file = await context.bot.get_file(doc.file_id)
                # Скачиваем во временный файл с оригинальным расширением, потом конвертируем в PNG
                raw_path = os.path.join(config.TEMP_DIR, f"temp_watermark_raw_{user_id}{os.path.splitext(file_name)[1]}")
                await file.download_to_drive(raw_path)
                logger.info(f"Downloaded raw file to: {raw_path}, exists: {os.path.exists(raw_path)}")

                # Конвертируем в PNG чтобы сохранить прозрачность
                img = Image.open(raw_path).convert("RGBA")
                img.save(temp_path, "PNG")
                logger.info(f"Converted to PNG: {temp_path}, exists: {os.path.exists(temp_path)}")

            else:
                await update.message.reply_text(
                    "❌ Пожалуйста, отправьте фото или PNG-файл ватермарки!"
                )
                return WAITING_WATERMARK

            self.temp_watermark[user_id] = temp_path

            await update.message.reply_text(
                "✅ Ватермарк получен!\n\n"
                "Теперь введите название для этого ватермарка (например: slot1, logo, signature):"
            )
            return WAITING_SLOT_NAME
            
        finally:
            # Удаляем временный raw файл если он был создан
            if raw_path and os.path.exists(raw_path):
                try:
                    os.remove(raw_path)
                    logger.info(f"Removed temp raw file: {raw_path}")
                except Exception as e:
                    logger.error(f"Error removing temp raw file: {e}")

    async def receive_slot_name(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение названия слота"""
        user_id = update.effective_user.id
        slot_name = update.message.text.strip()
        
        # Проверка корректности названия
        if not slot_name or len(slot_name) > 50:
            await update.message.reply_text(
                "❌ Название должно быть от 1 до 50 символов. Попробуйте еще раз:"
            )
            return WAITING_SLOT_NAME
        
        # Сохраняем название во временные данные
        context.user_data['slot_name'] = slot_name
        
        await update.message.reply_text(
            "Отлично! Теперь укажите прозрачность водяного знака.\n\n"
            "Введите число от 1 до 100:\n"
            "• 1 = почти невидимый\n"
            "• 50 = полупрозрачный\n"
            "• 100 = полностью непрозрачный\n\n"
            "Рекомендуется: 30-50 для фона, 80-100 для яркого текста"
        )
        return WAITING_OPACITY

    async def receive_opacity(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение прозрачности водяного знака"""
        user_id = update.effective_user.id
        
        try:
            opacity = int(update.message.text.strip())
            
            if opacity < 1 or opacity > 100:
                await update.message.reply_text(
                    "❌ Прозрачность должна быть от 1 до 100. Попробуйте еще раз:"
                )
                return WAITING_OPACITY
            
            slot_name = context.user_data.get('slot_name')
            if not slot_name:
                await update.message.reply_text("❌ Ошибка: название не найдено. Начните заново с /add_watermark")
                return ConversationHandler.END
            
            # Сохраняем ватермарк
            if user_id not in self.user_watermarks:
                self.user_watermarks[user_id] = {}
            if user_id not in self.watermark_opacity:
                self.watermark_opacity[user_id] = {}
            
            # Перемещаем из временной папки в постоянную
            temp_path = self.temp_watermark.get(user_id)
            if not temp_path or not os.path.exists(temp_path):
                await update.message.reply_text("❌ Ошибка: ватермарк не найден. Начните заново с /add_watermark")
                return ConversationHandler.END
            
            final_path = os.path.join(config.WATERMARKS_DIR, f"{user_id}_{slot_name}.png")
            os.replace(temp_path, final_path)
            
            self.user_watermarks[user_id][slot_name] = final_path
            self.watermark_opacity[user_id][slot_name] = opacity
            
            await update.message.reply_text(
                f"✅ Ватермарк '{slot_name}' успешно сохранен с прозрачностью {opacity}%!\n\n"
                f"Теперь вы можете использовать его командой /apply"
            )
            
            # Очищаем временные данные
            if user_id in self.temp_watermark:
                del self.temp_watermark[user_id]
            if 'slot_name' in context.user_data:
                del context.user_data['slot_name']
            
            return ConversationHandler.END
            
        except ValueError:
            await update.message.reply_text(
                "❌ Пожалуйста, введите число от 1 до 100:"
            )
            return WAITING_OPACITY

    async def list_watermarks(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать список ватермарков пользователя"""
        user_id = update.effective_user.id
        
        # Проверка доступа
        if not self.check_access(user_id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
        
        if user_id not in self.user_watermarks or not self.user_watermarks[user_id]:
            await update.message.reply_text(
                "У вас пока нет сохраненных ватермарков.\n"
                "Добавьте первый с помощью /add_watermark"
            )
            return
        
        watermarks_list = "\n".join([f"• {name}" for name in self.user_watermarks[user_id].keys()])
        await update.message.reply_text(
            f"📋 Ваши ватермарки:\n\n{watermarks_list}\n\n"
            f"Используйте /apply для наложения ватермарка"
        )

    async def apply_watermark_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало процесса наложения ватермарка"""
        user_id = update.effective_user.id
        
        # Проверка доступа
        if not self.check_access(user_id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return ConversationHandler.END
        
        if user_id not in self.user_watermarks or not self.user_watermarks[user_id]:
            await update.message.reply_text(
                "❌ У вас нет сохраненных ватермарков.\n"
                "Сначала добавьте ватермарк с помощью /add_watermark"
            )
            return ConversationHandler.END
        
        # Создаем клавиатуру с ватермарками
        keyboard = [[name] for name in self.user_watermarks[user_id].keys()]
        keyboard.append(["Отмена"])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            "Выберите ватермарк, который хотите наложить:",
            reply_markup=reply_markup
        )
        return WAITING_PHOTO

    async def receive_photo_for_watermark(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Получение фото для наложения ватермарка"""
        user_id = update.effective_user.id
        
        # Проверка на отмену
        if update.message.text and update.message.text == "Отмена":
            await update.message.reply_text("❌ Операция отменена.", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        
        # Если это текст (выбор ватермарка)
        if update.message.text:
            slot_name = update.message.text.strip()
            
            if user_id not in self.user_watermarks or slot_name not in self.user_watermarks[user_id]:
                await update.message.reply_text("❌ Ватермарк не найден. Попробуйте еще раз:")
                return WAITING_PHOTO
            
            context.user_data['selected_watermark'] = slot_name
            await update.message.reply_text(
                f"✅ Выбран ватермарк: {slot_name}\n\n"
                "Теперь отправьте фото, на которое нужно наложить ватермарк:",
                reply_markup=ReplyKeyboardRemove()
            )
            return WAITING_PHOTO
        
        # Если это фото
        if update.message.photo:
            selected_watermark = context.user_data.get('selected_watermark')
            
            if not selected_watermark:
                await update.message.reply_text("❌ Сначала выберите ватермарк из списка.")
                return WAITING_PHOTO
            
            await update.message.reply_text("⏳ Обрабатываю фото...")
            
            main_photo_path = None
            result_path = None
            
            try:
                # Скачиваем основное фото
                photo = update.message.photo[-1]
                file = await context.bot.get_file(photo.file_id)
                main_photo_path = os.path.join(config.TEMP_DIR, f"main_{user_id}.jpg")
                await file.download_to_drive(main_photo_path)
                
                # Путь к ватермарку
                watermark_path = self.user_watermarks[user_id][selected_watermark]
                
                # Получаем прозрачность для этого водяного знака (по умолчанию 97%)
                opacity = self.watermark_opacity.get(user_id, {}).get(selected_watermark, 97)
                
                # Накладываем ватермарк
                result_path = self.apply_watermark_to_image(main_photo_path, watermark_path, user_id, opacity)
                
                # Отправляем результат как документ для сохранения качества
                with open(result_path, 'rb') as photo_file:
                    await update.message.reply_document(
                        document=photo_file,
                        filename=f"watermarked_{selected_watermark}.png",
                        caption=f"✅ Ватермарк '{selected_watermark}' успешно наложен!"
                    )
                
                # Очищаем данные
                if 'selected_watermark' in context.user_data:
                    del context.user_data['selected_watermark']
                
                await update.message.reply_text(
                    "Хотите наложить еще один ватермарк? Используйте /apply"
                )
                
                return ConversationHandler.END
                
            except Exception as e:
                logger.error(f"Error applying watermark: {e}")
                await update.message.reply_text(
                    f"❌ Произошла ошибка при обработке фото: {str(e)}\n"
                    "Попробуйте еще раз."
                )
                return ConversationHandler.END
            finally:
                # Удаляем временные файлы в любом случае
                if main_photo_path and os.path.exists(main_photo_path):
                    try:
                        os.remove(main_photo_path)
                        logger.info(f"Removed temp file: {main_photo_path}")
                    except Exception as e:
                        logger.error(f"Error removing temp file: {e}")
                if result_path and os.path.exists(result_path):
                    try:
                        os.remove(result_path)
                        logger.info(f"Removed temp file: {result_path}")
                    except Exception as e:
                        logger.error(f"Error removing temp file: {e}")
        
        # Если это документ (файл)
        if update.message.document:
            selected_watermark = context.user_data.get('selected_watermark')
            
            if not selected_watermark:
                await update.message.reply_text("❌ Сначала выберите ватермарк из списка.")
                return WAITING_PHOTO
            
            doc = update.message.document
            mime = doc.mime_type or ""
            file_name = doc.file_name or ""
            
            logger.info(f"Document received for watermarking: mime={mime}, file_name={file_name}")
            
            if not (mime in ("image/png", "image/jpeg", "image/jpg", "image/webp")
                    or file_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))):
                await update.message.reply_text(
                    "❌ Поддерживаются только файлы PNG, JPG, WEBP.\n"
                    "Отправьте фото или файл изображения:"
                )
                return WAITING_PHOTO
            
            await update.message.reply_text("⏳ Обрабатываю файл...")
            
            main_photo_path = None
            result_path = None
            
            try:
                # Скачиваем файл
                file = await context.bot.get_file(doc.file_id)
                main_photo_path = os.path.join(config.TEMP_DIR, f"main_{user_id}{os.path.splitext(file_name)[1]}")
                await file.download_to_drive(main_photo_path)
                logger.info(f"Downloaded main photo to: {main_photo_path}")
                
                # Путь к ватермарку
                watermark_path = self.user_watermarks[user_id][selected_watermark]
                
                # Получаем прозрачность для этого водяного знака (по умолчанию 97%)
                opacity = self.watermark_opacity.get(user_id, {}).get(selected_watermark, 97)
                
                # Накладываем ватермарк
                result_path = self.apply_watermark_to_image(main_photo_path, watermark_path, user_id, opacity)
                
                # Отправляем результат как документ для сохранения качества
                with open(result_path, 'rb') as photo_file:
                    await update.message.reply_document(
                        document=photo_file,
                        filename=f"watermarked_{selected_watermark}.png",
                        caption=f"✅ Ватермарк '{selected_watermark}' успешно наложен!"
                    )
                
                # Очищаем данные
                if 'selected_watermark' in context.user_data:
                    del context.user_data['selected_watermark']
                
                await update.message.reply_text(
                    "Хотите наложить еще один ватермарк? Используйте /apply"
                )
                
                return ConversationHandler.END
                
            except Exception as e:
                logger.error(f"Error applying watermark to document: {e}")
                await update.message.reply_text(
                    f"❌ Произошла ошибка при обработке файла: {str(e)}\n"
                    "Попробуйте еще раз."
                )
                return ConversationHandler.END
            finally:
                # Удаляем временные файлы в любом случае
                if main_photo_path and os.path.exists(main_photo_path):
                    try:
                        os.remove(main_photo_path)
                        logger.info(f"Removed temp file: {main_photo_path}")
                    except Exception as e:
                        logger.error(f"Error removing temp file: {e}")
                if result_path and os.path.exists(result_path):
                    try:
                        os.remove(result_path)
                        logger.info(f"Removed temp file: {result_path}")
                    except Exception as e:
                        logger.error(f"Error removing temp file: {e}")
        
        await update.message.reply_text("❌ Пожалуйста, отправьте фото или файл изображения!")
        return WAITING_PHOTO

    def apply_watermark_to_image(self, main_photo_path, watermark_path, user_id, opacity_percent):
        """Наложение ватермарка на фото — растягивается на весь размер"""
        from PIL import ImageChops

        # Открываем основное фото
        main_image = Image.open(main_photo_path).convert("RGBA")
        main_width, main_height = main_image.size
        logger.info(f"Main image size: {main_width}x{main_height}")

        # Открываем ватермарку
        watermark = Image.open(watermark_path).convert("RGBA")
        wm_width, wm_height = watermark.size
        logger.info(f"Watermark original size: {wm_width}x{wm_height}")

        # Проверяем размер фото - если маленькое, используем пропорциональное масштабирование
        MIN_SIZE = 800  # минимальный размер для растягивания
        
        if main_width < MIN_SIZE or main_height < MIN_SIZE:
            # Для маленьких фото - пропорциональное масштабирование на всю ширину
            logger.info(f"Small photo detected ({main_width}x{main_height}), using proportional scaling")
            target_width = main_width
            scale_factor = target_width / wm_width
            target_height = int(wm_height * scale_factor)
            
            watermark_resized = watermark.resize((target_width, target_height), Image.Resampling.LANCZOS)
            logger.info(f"Watermark resized proportionally to: {target_width}x{target_height}")

            # Применяем прозрачность к альфа-каналу
            r, g, b, a = watermark_resized.split()
            
            if opacity_percent == 100:
                # При 100% делаем только ПОЛНОСТЬЮ непрозрачные пиксели (альфа=255) видимыми
                # Остальные (полупрозрачные артефакты) убираем
                a = a.point(lambda p: 255 if p > 250 else 0)
                watermark_resized = Image.merge('RGBA', (r, g, b, a))
                logger.info(f"Opacity 100% - only fully opaque pixels visible")
            else:
                # Умножаем альфа-канал на процент прозрачности
                opacity_multiplier = opacity_percent / 100.0
                a = a.point(lambda p: int(p * opacity_multiplier))
                watermark_resized = Image.merge('RGBA', (r, g, b, a))
                logger.info(f"Applied opacity: {opacity_percent}% (colors preserved)")

            # Создаем прозрачный слой размером с основное фото
            overlay = Image.new('RGBA', (main_width, main_height), (0, 0, 0, 0))
            
            # Размещаем водяной знак по центру вертикально
            x_position = 0
            y_position = (main_height - target_height) // 2
            overlay.paste(watermark_resized, (x_position, y_position), watermark_resized)
            logger.info(f"Watermark positioned at: ({x_position}, {y_position})")
        else:
            # Для больших фото - растягиваем на всю ширину и высоту
            logger.info(f"Large photo detected ({main_width}x{main_height}), stretching to full size")
            watermark_resized = watermark.resize((main_width, main_height), Image.Resampling.LANCZOS)
            logger.info(f"Watermark resized to full image size: {main_width}x{main_height}")

            # Применяем прозрачность к альфа-каналу
            r, g, b, a = watermark_resized.split()
            
            if opacity_percent == 100:
                # При 100% делаем только ПОЛНОСТЬЮ непрозрачные пиксели (альфа=255) видимыми
                # Остальные (полупрозрачные артефакты) убираем
                a = a.point(lambda p: 255 if p > 250 else 0)
                watermark_resized = Image.merge('RGBA', (r, g, b, a))
                logger.info(f"Opacity 100% - only fully opaque pixels visible")
            else:
                # Умножаем альфа-канал на процент прозрачности
                opacity_multiplier = opacity_percent / 100.0
                a = a.point(lambda p: int(p * opacity_multiplier))
                watermark_resized = Image.merge('RGBA', (r, g, b, a))
                logger.info(f"Applied opacity: {opacity_percent}% (colors preserved)")

            # Создаем прозрачный слой размером с основное фото
            overlay = Image.new('RGBA', (main_width, main_height), (0, 0, 0, 0))
            
            # Размещаем водяной знак на весь размер
            overlay.paste(watermark_resized, (0, 0), watermark_resized)
            logger.info(f"Watermark positioned to cover full image")

        # Накладываем водяной знак на основное фото
        logger.info(f"Before composite - main_image mode: {main_image.mode}, overlay mode: {overlay.mode}")
        logger.info(f"Before composite - main_image size: {main_image.size}, overlay size: {overlay.size}")
        
        result = Image.alpha_composite(main_image, overlay)
        logger.info(f"After composite - result mode: {result.mode}, result size: {result.size}")

        # Сохраняем как PNG для максимального качества
        result_path = os.path.join(config.TEMP_DIR, f"result_{user_id}.png")
        result.save(result_path, "PNG", optimize=False)
        logger.info(f"Saved result as PNG with maximum quality")

        return result_path

    async def delete_watermark_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Удаление ватермарка"""
        user_id = update.effective_user.id
        
        # Проверка доступа
        if not self.check_access(user_id):
            await update.message.reply_text("❌ У вас нет доступа к этому боту.")
            return
        
        if user_id not in self.user_watermarks or not self.user_watermarks[user_id]:
            await update.message.reply_text("У вас нет сохраненных ватермарков.")
            return
        
        # Создаем клавиатуру с ватермарками
        keyboard = [[name] for name in self.user_watermarks[user_id].keys()]
        keyboard.append(["Отмена"])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            "Выберите ватермарк для удаления:",
            reply_markup=reply_markup
        )

    # ============ АДМИН ПАНЕЛЬ ============
    
    async def admin_panel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Админ панель управления доступом"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав администратора.")
            return
        
        keyboard = [
            ["➕ Добавить пользователя"],
            ["➖ Удалить пользователя"],
            ["📋 Список пользователей"],
            ["❌ Закрыть"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "👑 Админ панель\n\n"
            "Выберите действие:",
            reply_markup=reply_markup
        )

    async def admin_add_user_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало добавления пользователя"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав администратора.")
            return ConversationHandler.END
        
        await update.message.reply_text(
            "Введите username пользователя (без @) или его Telegram ID:\n"
            "Например: username или 123456789\n\n"
            "Нажмите /cancel для отмены.",
            reply_markup=ReplyKeyboardRemove()
        )
        return WAITING_USERNAME_TO_ADD

    async def admin_add_user_process(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка добавления пользователя"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав администратора.")
            return ConversationHandler.END
        
        input_text = update.message.text.strip()
        
        # Проверяем это ID или username
        if input_text.isdigit():
            # Это ID
            target_user_id = int(input_text)
            self.db.add_user(target_user_id, None, None)
            await update.message.reply_text(
                f"✅ Пользователь с ID {target_user_id} добавлен!\n"
                "Он сможет использовать бота после команды /start"
            )
        else:
            # Это username - сохраняем для будущей идентификации
            # Пользователь будет добавлен когда напишет боту
            await update.message.reply_text(
                f"⚠️ Для добавления по username, пользователь @{input_text} должен написать боту /start\n"
                "Или используйте его Telegram ID для немедленного добавления."
            )
        
        return ConversationHandler.END

    async def admin_remove_user_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Начало удаления пользователя"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав администратора.")
            return ConversationHandler.END
        
        users = self.db.get_all_users()
        if not users:
            await update.message.reply_text("📋 Список пользователей пуст.")
            return ConversationHandler.END
        
        # Создаем клавиатуру с пользователями
        keyboard = []
        for user in users:
            if user['user_id'] == config.ADMIN_ID:
                continue  # Не показываем админа
            username = f"@{user['username']}" if user['username'] else "Без username"
            name = user['first_name'] or "Неизвестно"
            keyboard.append([f"{name} ({username}) - ID: {user['user_id']}"])
        
        keyboard.append(["❌ Отмена"])
        reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True, resize_keyboard=True)
        
        await update.message.reply_text(
            "Выберите пользователя для удаления:",
            reply_markup=reply_markup
        )
        return WAITING_USER_ID_TO_REMOVE

    async def admin_remove_user_process(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка удаления пользователя"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав администратора.")
            return ConversationHandler.END
        
        text = update.message.text
        
        if text == "❌ Отмена":
            await update.message.reply_text("Отменено.", reply_markup=ReplyKeyboardRemove())
            return ConversationHandler.END
        
        # Извлекаем ID из текста
        try:
            target_user_id = int(text.split("ID: ")[1])
            
            if target_user_id == config.ADMIN_ID:
                await update.message.reply_text("❌ Нельзя удалить администратора!")
                return ConversationHandler.END
            
            self.db.remove_user(target_user_id)
            await update.message.reply_text(
                f"✅ Пользователь с ID {target_user_id} удален!",
                reply_markup=ReplyKeyboardRemove()
            )
        except (IndexError, ValueError):
            await update.message.reply_text(
                "❌ Ошибка при удалении пользователя.",
                reply_markup=ReplyKeyboardRemove()
            )
        
        return ConversationHandler.END

    async def admin_list_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Список всех пользователей с доступом"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            await update.message.reply_text("❌ У вас нет прав администратора.")
            return
        
        users = self.db.get_all_users()
        
        if not users:
            await update.message.reply_text("📋 Список пользователей пуст.")
            return
        
        message = "📋 Пользователи с доступом:\n\n"
        for user in users:
            username = f"@{user['username']}" if user['username'] else "Без username"
            name = user['first_name'] or "Неизвестно"
            is_admin = " 👑" if user['user_id'] == config.ADMIN_ID else ""
            message += f"• {name} ({username}){is_admin}\n  ID: {user['user_id']}\n  Добавлен: {user['added_at']}\n\n"
        
        await update.message.reply_text(message)

    async def admin_panel_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопок админ панели"""
        user_id = update.effective_user.id
        
        if not self.is_admin(user_id):
            return
        
        text = update.message.text
        
        if text == "➕ Добавить пользователя":
            return await self.admin_add_user_start(update, context)
        elif text == "➖ Удалить пользователя":
            return await self.admin_remove_user_start(update, context)
        elif text == "📋 Список пользователей":
            await self.admin_list_users(update, context)
        elif text == "❌ Закрыть":
            await update.message.reply_text("Админ панель закрыта.", reply_markup=ReplyKeyboardRemove())

    async def cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Отмена операции"""
        await update.message.reply_text(
            "❌ Операция отменена.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END


def main():
    """Запуск бота"""
    bot = WatermarkBot()
    
    # Создаем приложение
    application = Application.builder().token(config.BOT_TOKEN).build()
    
    # Обработчик добавления ватермарка
    add_watermark_handler = ConversationHandler(
        entry_points=[CommandHandler('add_watermark', bot.add_watermark_start)],
        states={
            WAITING_WATERMARK: [
                MessageHandler(filters.PHOTO, bot.receive_watermark),
                MessageHandler(filters.Document.ALL, bot.receive_watermark),
            ],
            WAITING_SLOT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_slot_name)],
            WAITING_OPACITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_opacity)],
        },
        fallbacks=[CommandHandler('cancel', bot.cancel)],
    )
    
    # Обработчик применения ватермарка
    apply_watermark_handler = ConversationHandler(
        entry_points=[CommandHandler('apply', bot.apply_watermark_start)],
        states={
            WAITING_PHOTO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, bot.receive_photo_for_watermark),
                MessageHandler(filters.PHOTO, bot.receive_photo_for_watermark),
                MessageHandler(filters.Document.ALL, bot.receive_photo_for_watermark)
            ],
        },
        fallbacks=[CommandHandler('cancel', bot.cancel)],
    )
    
    # Обработчик добавления пользователя админом
    admin_add_user_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➕ Добавить пользователя$"), bot.admin_add_user_start)],
        states={
            WAITING_USERNAME_TO_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.admin_add_user_process)],
        },
        fallbacks=[CommandHandler('cancel', bot.cancel)],
    )
    
    # Обработчик удаления пользователя админом
    admin_remove_user_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^➖ Удалить пользователя$"), bot.admin_remove_user_start)],
        states={
            WAITING_USER_ID_TO_REMOVE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bot.admin_remove_user_process)],
        },
        fallbacks=[CommandHandler('cancel', bot.cancel)],
    )
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler('start', bot.start))
    application.add_handler(CommandHandler('help', bot.help_command))
    application.add_handler(CommandHandler('admin', bot.admin_panel))
    application.add_handler(add_watermark_handler)
    application.add_handler(apply_watermark_handler)
    application.add_handler(admin_add_user_handler)
    application.add_handler(admin_remove_user_handler)
    application.add_handler(MessageHandler(filters.Regex("^(📋 Список пользователей|❌ Закрыть)$"), bot.admin_panel_handler))
    application.add_handler(CommandHandler('list_watermarks', bot.list_watermarks))
    application.add_handler(CommandHandler('delete_watermark', bot.delete_watermark_start))
    
    # Запускаем бота
    logger.info("Бот запущен!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
