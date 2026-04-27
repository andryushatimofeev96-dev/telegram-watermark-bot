# Создание GitHub репозитория

## Шаг 1: Установка Git

### Windows:
1. Скачайте Git с официального сайта: https://git-scm.com/download/win
2. Запустите установщик
3. Используйте настройки по умолчанию
4. Перезапустите терминал после установки

### Проверка установки:
```bash
git --version
```

## Шаг 2: Настройка Git (первый раз)

```bash
git config --global user.name "Ваше Имя"
git config --global user.email "ваш@email.com"
```

## Шаг 3: Создание репозитория на GitHub

1. Откройте https://github.com
2. Войдите в свой аккаунт (или создайте новый)
3. Нажмите кнопку "+" в правом верхнем углу
4. Выберите "New repository"
5. Заполните:
   - **Repository name**: `telegram-watermark-bot` (или любое другое название)
   - **Description**: `Telegram bot for adding watermarks to photos`
   - **Public** или **Private** (на ваш выбор)
   - ❌ НЕ ставьте галочки "Add README", "Add .gitignore", "Choose a license" (у нас уже есть эти файлы)
6. Нажмите "Create repository"

## Шаг 4: Инициализация локального репозитория

Откройте терминал в папке проекта (`C:\Users\New\Desktop\watermark`) и выполните:

```bash
# Инициализация Git
git init

# Добавление всех файлов (кроме тех что в .gitignore)
git add .

# Первый коммит
git commit -m "Initial commit: Telegram watermark bot with SQLite"

# Переименование ветки в main (если нужно)
git branch -M main

# Добавление удаленного репозитория (замените YOUR_USERNAME и YOUR_REPO)
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git

# Отправка кода на GitHub
git push -u origin main
```

## Шаг 5: Замена YOUR_USERNAME и YOUR_REPO

После создания репозитория на GitHub, вы увидите URL вида:
```
https://github.com/username/telegram-watermark-bot.git
```

Используйте этот URL в команде `git remote add origin`

## Пример полной последовательности команд:

```bash
cd C:\Users\New\Desktop\watermark
git init
git add .
git commit -m "Initial commit: Telegram watermark bot with SQLite"
git branch -M main
git remote add origin https://github.com/yourusername/telegram-watermark-bot.git
git push -u origin main
```

## Важно! Проверьте .gitignore

Убедитесь что файл `.gitignore` содержит:

```
# Конфигурация (содержит токен)
config.py

# База данных SQLite
*.db
*.db-journal

# Папки бота
watermarks/
temp/
```

Это защитит ваш токен бота и личные данные от публикации!

## Что будет загружено на GitHub:

✅ Исходный код бота (`bot.py`, `database.py`)
✅ Документация (`README.md`, `QUICKSTART.md`, и т.д.)
✅ Зависимости (`requirements.txt`)
✅ Пример конфигурации (`config.example.py`)
✅ `.gitignore`

❌ НЕ будет загружено:
- `config.py` (содержит токен)
- `bot_database.db` (база данных)
- Папки `watermarks/` и `temp/`
- `__pycache__/`

## Обновление репозитория в будущем:

```bash
# Добавить изменения
git add .

# Создать коммит
git commit -m "Описание изменений"

# Отправить на GitHub
git push
```

## Клонирование репозитория на другом компьютере:

```bash
# Клонировать репозиторий
git clone https://github.com/yourusername/telegram-watermark-bot.git

# Перейти в папку
cd telegram-watermark-bot

# Скопировать пример конфигурации
copy config.example.py config.py

# Отредактировать config.py и указать свой токен

# Установить зависимости
pip install -r requirements.txt

# Запустить бота
python bot.py
```

## Полезные команды Git:

```bash
# Проверить статус
git status

# Посмотреть историю коммитов
git log

# Посмотреть изменения
git diff

# Отменить изменения в файле
git checkout -- filename

# Посмотреть удаленные репозитории
git remote -v
```

## Если нужна помощь:

- Документация Git: https://git-scm.com/doc
- GitHub Guides: https://guides.github.com/
- GitHub Desktop (GUI): https://desktop.github.com/ (если не хотите использовать командную строку)
