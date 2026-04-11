# Finance Mini App Backend

Backend на `FastAPI` + `SQLAlchemy` для проекта `finance-miniapp`.

## Что в репозитории

- API для операций, категорий, целей, аналитики и recurring expenses
- Telegram-бот на `aiogram`
- Railway-конфиги для постоянного деплоя API и bot runtime

## Локальный запуск

1. Создай `.env` на основе `.env.example`
2. Установи зависимости
3. Запусти API и бота отдельными процессами

```bash
cd /Users/n.smurova/finance-miniapp-backend
python3 -m pip install setuptools wheel
python3 -m pip install -e .
uvicorn app.main:app --reload
```

Отдельным терминалом:

```bash
cd /Users/n.smurova/finance-miniapp-backend
python3 -m app.bot.main
```

Проверка API:

```bash
curl http://127.0.0.1:8000/health
```

Если `api.telegram.org` недоступен из локальной сети, для бота можно указать proxy:

```env
TELEGRAM_PROXY=socks5://user:pass@host:1080
```

или

```env
TELEGRAM_PROXY=http://user:pass@host:8080
```

## Railway без временных туннелей

Из backend-репозитория поднимаются два отдельных сервиса:

1. `finance-miniapp-api`
   Используй корневой конфиг `railway.toml`
2. `finance-miniapp-bot`
   В Railway Settings укажи custom config path: `/railway.bot.toml`

Оба сервиса собираются через Railpack и получают стартовые команды из config-as-code.

### Переменные для API

```env
DATABASE_URL=postgresql+psycopg://postgres:user@host:5432/finance_miniapp
DEFAULT_TELEGRAM_ID=448027140
BOT_TOKEN=...
DEBUG=false
CORS_ALLOWED_ORIGINS=https://<frontend-domain>
```

### Переменные для Bot

```env
BOT_TOKEN=...
BACKEND_BASE_URL=https://<api-domain>/api/v1
MINI_APP_URL=https://<frontend-domain>
DEBUG=false
```

`DATABASE_URL` боту не нужен, если он работает только как Telegram runtime и ходит в API по `BACKEND_BASE_URL`.

## Текущая схема auth

Внутри Telegram Mini App backend проверяет сырой `Telegram.WebApp.initData` по `BOT_TOKEN`.

Для локального браузерного режима fallback остается через заголовок:

```text
X-Telegram-Id: 448027140
```

Если заголовок не передан, backend использует `DEFAULT_TELEGRAM_ID` из `.env`.
