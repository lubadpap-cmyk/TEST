# Telegram bot deployment on Square Cloud

## Что нужно сделать

1. Загрузите весь проект в Square Cloud.
2. В корне проекта должен быть файл squarecloud.yaml.
3. В поле BOT_TOKEN вставьте токен вашего Telegram-бота.
4. В поле ADMIN_ID вставьте ваш Telegram user ID.
5. Нажмите Deploy.

## Важные замечания

- Бот использует SQLite, файл базы создаётся автоматически в корне проекта.
- Для работы нужен Python 3.11.
- Запуск идёт через файл bot.py.
