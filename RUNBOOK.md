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
```

Если бот запускается локально и Telegram API из сети не режется:

```bash
cd /Users/n.smurova/finance-miniapp-backend
python3 -m app.bot.main
```

Если `api.telegram.org` недоступен локально, вынеси bot runtime в Railway и оставь API локально или тоже вынеси его отдельно.

## 4. Стабильный деплой без туннелей

### Backend repo

Подними два Railway services из `finance-miniapp-backend`:

1. API service
   Конфиг: `/railway.toml`
2. Bot service
   Конфиг: `/railway.bot.toml`

Переменные API service:

```env
DATABASE_URL=postgresql+psycopg://postgres:user@host:5432/finance_miniapp
DEFAULT_TELEGRAM_ID=448027140
BOT_TOKEN=...
DEBUG=false
CORS_ALLOWED_ORIGINS=https://<frontend-domain>
```

Переменные Bot service:

```env
BOT_TOKEN=...
BACKEND_BASE_URL=https://<api-domain>/api/v1
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

## 5. Smoke Test

1. Открой чат с ботом и выполни `/start`
2. Нажми `Открыть приложение`
3. В Mini App создай расход
4. В чате отправь `кофе 320`
5. Выполни `Сводка за месяц`
6. Выполни `Цели и накопления`
7. Проверь, что данные видны и в боте, и в Mini App

## 6. Следующий технический долг

- постоянный prod-домен вместо временного Railway subdomain
- редактирование и возвраты из интерфейса
