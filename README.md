# Finance Mini App Backend

Backend на `FastAPI` + `SQLAlchemy` для проекта `finance-miniapp`.

## Что в репозитории

- API для операций, категорий, целей, аналитики и recurring expenses
- Telegram-бот на `aiogram`
- конфиги деплоя для Vercel, Railway и Render

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
python3 scripts/smoke_test_api.py
```

Если `api.telegram.org` недоступен из локальной сети, для бота можно указать proxy:

```env
TELEGRAM_PROXY=socks5://user:pass@host:1080
```

или

```env
TELEGRAM_PROXY=http://user:pass@host:8080
```

## Production на Vercel

Текущая production-схема для backend: один Vercel deployment с `FastAPI` и Telegram webhook runtime внутри приложения.

Обязательные env:

```env
DATABASE_URL=postgresql+psycopg://postgres:<password>@<host>/<db>?sslmode=require
BOT_TOKEN=...
INTERNAL_API_KEY=...
BOT_MODE=webhook
PUBLIC_BASE_URL=https://<backend-domain>
TELEGRAM_WEBHOOK_SECRET=<shared-random-secret>
MINI_APP_URL=https://<frontend-domain>
CORS_ALLOWED_ORIGINS=https://<frontend-domain>
DEBUG=false
```

Поведение runtime:

- backend отвечает на `/health`, даже если настройка webhook при старте упала;
- при успешном старте приложение синхронно регистрирует webhook на
  `PUBLIC_BASE_URL + /telegram/webhook`;
- в webhook-режиме bot runtime по умолчанию ходит во внутренний API через тот же backend runtime.

Проверки после деплоя или рестарта:

```bash
curl --max-time 20 -i https://<backend-domain>/health
curl -sS "https://api.telegram.org/bot${BOT_TOKEN}/getWebhookInfo"
```

Ожидаемый webhook URL:

```text
https://<backend-domain>/telegram/webhook
```

Для production deploy из backend-репозитория:

```bash
npm_config_cache=/tmp/.npm-vercel-sync npx vercel deploy --prod --yes
```

Автоматическая проверка после deploy/restart:

```bash
python3 scripts/smoke_check_prod.py
```

Сейчас этот smoke дополнительно проверяет:

- signed `Telegram initData` на production API;
- отказ webhook endpoint без `X-Telegram-Bot-Api-Secret-Token`.

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
BOT_TOKEN=...
INTERNAL_API_KEY=...
DEBUG=false
CORS_ALLOWED_ORIGINS=https://<frontend-domain>
```

### Переменные для Bot

```env
BOT_TOKEN=...
BACKEND_BASE_URL=https://<api-domain>/api/v1
INTERNAL_API_KEY=...
MINI_APP_URL=https://<frontend-domain>
DEBUG=false
```

`DATABASE_URL` боту не нужен, если он работает только как Telegram runtime и ходит в API по `BACKEND_BASE_URL`.

## Текущая схема auth

Внутри Telegram Mini App backend принимает только подписанный `Telegram.WebApp.initData`.

Telegram-бот ходит в API по отдельному внутреннему ключу:

```text
X-Internal-Api-Key: <INTERNAL_API_KEY>
X-Telegram-Id: <telegram user id>
```

Небезопасный browser fallback через `X-Telegram-Id` разрешен только в локальной разработке при
`DEBUG=true` и `ALLOW_INSECURE_DEV_AUTH=true`.
