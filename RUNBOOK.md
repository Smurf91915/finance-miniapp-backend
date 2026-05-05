# End-to-End Runbook

## 1. Backend API

```bash
cd /Users/n.smurova/finance-miniapp-backend
python3 -m pip install setuptools wheel
python3 -m pip install -e .
uvicorn app.main:app --reload
```

Проверка:

```bash
curl http://127.0.0.1:8000/health
python3 scripts/smoke_test_api.py
```

Ожидаемый ответ:

```json
{"status":"ok"}
```

## 2. Frontend

```bash
cd /Users/n.smurova/finance-miniapp-frontend
npm install
npm run dev -- --host 0.0.0.0 --port 5173
```

Проверка:

- открой `http://127.0.0.1:5173`
- приложение должно загрузиться и показать дашборд

## 3. Telegram Bot

Заполни `.env` в backend:

```env
BOT_TOKEN=...
MINI_APP_URL=https://<frontend-public-url>
BACKEND_BASE_URL=http://127.0.0.1:8000/api/v1
INTERNAL_API_KEY=<shared-random-secret>
BOT_MODE=polling
```

Если бот запускается локально и Telegram API из сети не режется:

```bash
cd /Users/n.smurova/finance-miniapp-backend
python3 -m app.bot.main
```

Если `api.telegram.org` недоступен локально, вынеси bot runtime в Railway и оставь API локально или тоже вынеси его отдельно.

## 4. Стабильный деплой без туннелей

### Vercel: текущая production-схема

Backend может работать как один Vercel service вместе с Telegram webhook runtime.

Нужные env:

```env
DATABASE_URL=postgresql+psycopg://postgres:<password>@<host>/<db>?sslmode=require
BOT_TOKEN=...
INTERNAL_API_KEY=<shared-random-secret>
BOT_MODE=webhook
PUBLIC_BASE_URL=https://<backend-domain>
TELEGRAM_WEBHOOK_SECRET=<shared-random-secret>
MINI_APP_URL=https://<frontend-domain>
CORS_ALLOWED_ORIGINS=https://<frontend-domain>
DEBUG=false
```

Deploy:

```bash
cd /Users/n.smurova/finance-miniapp-backend
npm_config_cache=/tmp/.npm-vercel-sync npx vercel deploy --prod --yes
```

Проверка после deploy/restart:

```bash
python3 scripts/smoke_check_prod.py
```

Ожидаемое состояние:

- `/health` возвращает `200` и `{"status":"ok"}`
- `getWebhookInfo` возвращает `https://<backend-domain>/telegram/webhook`

### Railway: альтернативная схема

### Backend repo

Подними два Railway services из `finance-miniapp-backend`:

1. API service
   Конфиг: `/railway.toml`
2. Bot service
   Конфиг: `/railway.bot.toml`

Переменные API service:

```env
DATABASE_URL=postgresql+psycopg://postgres:user@host:5432/finance_miniapp
BOT_TOKEN=...
INTERNAL_API_KEY=<shared-random-secret>
DEBUG=false
CORS_ALLOWED_ORIGINS=https://<frontend-domain>
```

Переменные Bot service:

```env
BOT_TOKEN=...
BACKEND_BASE_URL=https://<api-domain>/api/v1
INTERNAL_API_KEY=<shared-random-secret>
MINI_APP_URL=https://<frontend-domain>
DEBUG=false
```

### Frontend repo

Подними отдельный Railway service из `finance-miniapp-frontend`.

Переменные:

```env
VITE_API_BASE_URL=https://<api-domain>/api/v1
```

После деплоя:

1. вставь frontend-домен в `MINI_APP_URL` bot service
2. вставь frontend-домен в `CORS_ALLOWED_ORIGINS` API service
3. redeploy API и Bot

## 5. Бесплатный стек без Railway

Бэкенд теперь умеет работать в одном web service вместе с Telegram-ботом через webhook. Для этого нужны такие переменные:

```env
DATABASE_URL=postgresql+psycopg://postgres:<password>@<host>/<db>?sslmode=require
BOT_TOKEN=...
INTERNAL_API_KEY=<shared-random-secret>
BOT_MODE=webhook
PUBLIC_BASE_URL=https://<backend-domain>
TELEGRAM_WEBHOOK_SECRET=<shared-random-secret>
MINI_APP_URL=https://<frontend-domain>
CORS_ALLOWED_ORIGINS=https://<frontend-domain>
DEBUG=false
```

`BACKEND_BASE_URL` в webhook-режиме можно не задавать: bot будет ходить в API через `127.0.0.1:$PORT`.

Для локального браузерного режима без Telegram включай fallback только явно:

```env
DEBUG=true
ALLOW_INSECURE_DEV_AUTH=true
DEFAULT_TELEGRAM_ID=<local-dev-user-id>
```

Схема миграции:

1. PostgreSQL перенести в Neon
2. frontend вынести на Render Static Site или Cloudflare Pages
3. backend + bot поднять одним web service на Render через `uvicorn app.main:app`

Подробный план смотри в `FREE_STACK_MIGRATION.md`.

## 6. Smoke Test

1. Открой чат с ботом и выполни `/start`
2. Нажми `Открыть приложение`
3. В Mini App создай расход
4. В чате отправь `кофе 320`
5. Выполни `Сводка за месяц`
6. Выполни `Цели и накопления`
7. Проверь, что данные видны и в боте, и в Mini App

## 7. Следующий технический долг

- автоматизировать post-deploy smoke check для `/health` и `getWebhookInfo`
- покрыть bot/webhook delivery и signed Telegram auth в автоматизированном smoke
