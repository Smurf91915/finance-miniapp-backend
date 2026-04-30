# Free Stack Migration

Цель: уехать с Railway на бесплатный стек без выделенного bot worker.

## Целевая схема

- frontend: Render Static Site или Cloudflare Pages
- database: Neon Postgres
- backend + Telegram bot: один web service на Render

Бот в этом режиме работает через webhook внутри FastAPI-приложения. Отдельный процесс `python -m app.bot.main` больше не нужен.

## 1. Frontend

`finance-miniapp-frontend` можно деплоить как обычный Vite static build.

Для Render в репозитории уже есть `render.yaml`. Если создавать сервис вручную, используй:

- build command: `npm run build`
- output directory: `dist`
- env: `VITE_API_BASE_URL=https://<backend-domain>/api/v1`

После деплоя нужен публичный frontend URL. Его потом ставим в:

- `MINI_APP_URL` у backend service
- `CORS_ALLOWED_ORIGINS` у backend service

## 2. Database

Создай базу в Neon и возьми connection string в формате `postgresql://...`.

Для backend используй SQLAlchemy-совместимый DSN:

```env
DATABASE_URL=postgresql+psycopg://postgres:<password>@<host>/<db>?sslmode=require
```

Если нужна загрузка текущих данных из локального Postgres:

```bash
pg_dump finance_miniapp > finance_miniapp.sql
psql "<neon-connection-string>" < finance_miniapp.sql
```

## 3. Backend + Bot

Бэкенд уже подготовлен под один web service. Нужные env:

```env
BOT_TOKEN=...
BOT_MODE=webhook
PUBLIC_BASE_URL=https://<backend-domain>
MINI_APP_URL=https://<frontend-domain>
CORS_ALLOWED_ORIGINS=https://<frontend-domain>
DEBUG=false
```

Опционально:

```env
TELEGRAM_WEBHOOK_SECRET=<random-secret>
```

Если `BACKEND_BASE_URL` не задан, bot runtime сам использует `http://127.0.0.1:$PORT/api/v1`.

### Start command

На Render можно использовать либо готовый `render.yaml`, либо Docker deploy из репозитория. В обоих случаях `app.main` сам:

- поднимет FastAPI
- запустит Telegram webhook runtime
- зарегистрирует webhook в Telegram
- примет обновления на `/telegram/webhook`

## 4. Docker Deploy

В репозитории есть `Dockerfile`, так что backend можно деплоить как обычный containerized web app.

Локальная проверка:

```bash
cd /Users/n.smurova/finance-miniapp-backend
docker build -t finance-miniapp-backend .
docker run --rm -p 8000:8000 --env-file .env finance-miniapp-backend
```

## 5. Render Checklist

### Backend

1. Создай `Web Service`
2. Подключи репозиторий `finance-miniapp-backend`
3. Либо импортируй `render.yaml`, либо выбери Docker runtime вручную
4. Заполни env:

```env
DATABASE_URL=postgresql+psycopg://finance_miniapp_owner:<password>@ep-...eu-central-1.aws.neon.tech/finance_miniapp?sslmode=require
BOT_TOKEN=...
BOT_MODE=webhook
PUBLIC_BASE_URL=https://<backend>.onrender.com
MINI_APP_URL=https://<frontend>.onrender.com
CORS_ALLOWED_ORIGINS=https://<frontend>.onrender.com
DEBUG=false
```

### Frontend

1. Создай `Static Site`
2. Подключи репозиторий `finance-miniapp-frontend`
3. Либо импортируй `render.yaml`, либо укажи вручную:

```env
VITE_API_BASE_URL=https://<backend>.onrender.com/api/v1
```

4. После первого деплоя скопируй frontend URL
5. Обнови `MINI_APP_URL` и `CORS_ALLOWED_ORIGINS` у backend service
6. Передеплой backend

## 6. Smoke Test

1. Открой `https://<backend-domain>/health`
2. Проверь, что frontend открывается
3. Выполни `/start` в Telegram
4. Нажми `Открыть приложение`
5. Создай расход в Mini App
6. Отправь боту `кофе 320`
7. Убедись, что операция видна и в истории, и в боте
