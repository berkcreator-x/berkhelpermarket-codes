# BerkHelperMarket

Telegram-бот для создания и улучшения продающих карточек товаров для маркетплейсов
**Wildberries, Ozon, Shopify** на базе **GPT-4o-mini** через **ProxyAPI**.

---

## Возможности

| Функция | Стоимость |
|---|---|
| 🆕 Новый товар — карточка с нуля по 4 параметрам | 1 генерация |
| ✨ Улучшить товар — улучшение существующего описания | 2 генерации |
| 👤 Профиль — баланс, статистика, тариф | бесплатно |
| 💳 Генерации — покупка пакетов через ЮMoney | — |
| ⚙️ Админ-панель — управление пользователями | только ADMIN_ID |

Новый пользователь получает **1 бесплатную генерацию**.

### Формат карточки

```
🏷 Название
📝 Описание
⭐ Преимущества
🔍 SEO-ключи
📦 Характеристики
```

### Пакеты генераций

| Пакет | Генераций | Цена |
|---|---|---|
| pack_10 | 10 | 149 ₽ |
| pack_50 | 50 | 599 ₽ |
| pack_150 | 150 | 1 499 ₽ |

---

## Стек

- **Python 3.12** + aiogram 3.x
- **PostgreSQL** + SQLAlchemy (async) + Alembic
- **Redis** — rate limiting + FSM storage
- **ProxyAPI** — OpenAI-compatible API, работает из РФ (`gpt-4o-mini`)
- **ЮMoney** — приём платежей
- **Docker / Docker Compose** — локальная разработка
- **Render** — production деплой
- **structlog** — структурированное логирование

---

## Быстрый старт

### 1. Клонировать и настроить окружение

```bash
git clone https://github.com/yourname/berkhelpermarket.git
cd berkhelpermarket
cp .env.example .env
```

Заполните `.env` (см. раздел «Переменные окружения» ниже).

### 2. Локальный запуск через Docker Compose

```bash
docker compose up --build
```

Миграции применяются автоматически при старте контейнера.

### 3. Локальный запуск без Docker

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
python main.py
```

При пустом `WEBHOOK_BASE_URL` бот запускается в режиме long-polling.

---

## Переменные окружения

Скопируйте `.env.example` в `.env` и заполните все значения:

```bash
cp .env.example .env
```

| Переменная | Обязательна | Описание |
|---|---|---|
| `BOT_TOKEN` | ✅ | Токен от [@BotFather](https://t.me/BotFather) |
| `ADMIN_ID` | ✅ | Ваш Telegram ID (доступ к ⚙️ Панели) |
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://user:pass@host:5432/db` |
| `REDIS_URL` | ✅ | `redis://host:6379/0` |
| `PROXYAPI_API_KEY` | ✅ | Ключ с [proxyapi.ru](https://proxyapi.ru) |
| `PROXYAPI_BASE_URL` | — | `https://api.proxyapi.ru/openai/v1` (по умолчанию) |
| `AI_MODEL` | — | `gpt-4o-mini` (по умолчанию) |
| `YOOMONEY_WALLET` | ✅ | Номер кошелька ЮMoney |
| `YOOMONEY_TOKEN` | ✅ | OAuth-токен ЮMoney |
| `YOOMONEY_SECRET` | ✅ | Секрет HTTP-уведомлений ЮMoney |
| `PAYMENT_SUCCESS_URL` | — | Ссылка на бота после оплаты (`https://t.me/YourBot`) |
| `WEBHOOK_BASE_URL` | — | Публичный URL (Render). Пусто → polling |
| `WEB_SERVER_PORT` | — | `8080` по умолчанию |
| `RATE_LIMIT_MESSAGES` | — | `5` сообщений |
| `RATE_LIMIT_PERIOD_SECONDS` | — | `10` секунд |
| `LOG_LEVEL` | — | `INFO` / `DEBUG` |

---

## Настройка ProxyAPI

1. Зарегистрируйтесь на [proxyapi.ru](https://proxyapi.ru)
2. Создайте API-ключ в личном кабинете
3. Пополните баланс (оплата картой РФ)
4. Добавьте в `.env`:
   ```
   PROXYAPI_API_KEY=sk-xxxxxxxx
   PROXYAPI_BASE_URL=https://api.proxyapi.ru/openai/v1
   AI_MODEL=gpt-4o-mini
   ```

ProxyAPI совместим с OpenAI API — замена модели делается одной строкой в `.env`.

---

## Настройка ЮMoney

1. Создайте кошелёк на [yoomoney.ru](https://yoomoney.ru)
2. Получите OAuth-токен: [инструкция](https://yoomoney.ru/docs/wallet/using-api/authorization/request)
   - Нужны права: `operation-history`, `account-info`
3. Настройте HTTP-уведомления в личном кабинете:
   - **URL:** `https://your-render-url.onrender.com/webhook/yoomoney`
   - **Секрет:** придумайте и запишите в `YOOMONEY_SECRET`
4. Добавьте в `.env`:
   ```
   YOOMONEY_WALLET=410011XXXXXXXXX
   YOOMONEY_TOKEN=your-oauth-token
   YOOMONEY_SECRET=your-secret
   PAYMENT_SUCCESS_URL=https://t.me/YourBotUsername
   ```

---

## Деплой на Render

### Шаг 1. Создать сервисы

В [Render Dashboard](https://dashboard.render.com) создайте:
- **PostgreSQL** — бесплатная БД (или внешняя)
- **Redis** — бесплатный Redis (или Upstash)
- **Web Service** — Docker runtime, из вашего репозитория

### Шаг 2. Переменные окружения

В Web Service → Environment добавьте **все** переменные из таблицы выше.

Render автоматически предоставляет Internal URLs для PostgreSQL и Redis — используйте их в `DATABASE_URL` и `REDIS_URL`.

### Шаг 3. Webhook

```
WEBHOOK_BASE_URL=https://berkhelpermarket.onrender.com
```

Telegram webhook установится автоматически при старте.

### Шаг 4. ЮMoney webhook

В настройках ЮMoney укажите:
```
https://berkhelpermarket.onrender.com/webhook/yoomoney
```

### Sleep mode (бесплатный тариф)

Render засыпает после ~15 мин без трафика. Система **полностью stateless**:
- FSM-состояния в Redis
- Баланс и платежи в PostgreSQL
- После пробуждения всё работает без потерь

Для уменьшения cold start добавьте `GET /health` в [UptimeRobot](https://uptimerobot.com) с интервалом 5 минут (бесплатно).

---

## Архитектура

```
src/
├── handlers/          # aiogram-роутеры
│   ├── common.py      # /start, /cancel, /menu
│   ├── new_product.py # 🆕 Новый товар (FSM, 4 шага)
│   ├── improve_product.py  # ✨ Улучшить товар
│   ├── profile.py     # 👤 Профиль
│   ├── generations.py # 💳 Генерации + оплата
│   ├── admin.py       # ⚙️ Админ-панель
│   └── states.py      # FSM-состояния
├── ai/
│   ├── proxyapi_client.py    # HTTP-клиент ProxyAPI (retry x3, backoff, timeout)
│   ├── prompt_builder.py     # Промпты для GPT-4o-mini
│   └── generation_service.py # Баланс → AI → списание (SELECT FOR UPDATE)
├── payments/
│   ├── yoomoney_client.py    # Quickpay URL + verify через API
│   ├── payment_service.py    # Создание/подтверждение платежей (идемпотентно)
│   └── webhook.py            # ЮMoney HTTP-уведомления (sha1 валидация)
├── database/          # SQLAlchemy engine + session
├── models/            # User, GenerationLog, Payment
├── repositories/      # Data access layer
├── middlewares/       # DBSession + RateLimit
└── config/            # pydantic-settings
```

---

## База данных

| Таблица | Ключевые поля |
|---|---|
| `users` | telegram_id, generation_balance (CHECK >= 0), plan |
| `generation_logs` | user_id, type (new/improve), created_at |
| `payments` | label (UNIQUE), status (pending/paid/failed), generations |

Миграции:
- `0001_initial` — создание таблиц
- `0002_check_balance` — `CHECK (generation_balance >= 0)`

---

## Безопасность

- Все секреты только в `.env`, который добавлен в `.gitignore`
- `PROXYAPI_API_KEY` и `YOOMONEY_TOKEN` **не логируются**
- Webhook ЮMoney проверяется по `sha1_hash`
- Подтверждение платежа идемпотентно (SELECT FOR UPDATE)
- Rate limiting: 5 сообщений / 10 сек (Redis)
- `CHECK (generation_balance >= 0)` на уровне БД
- Доступ к админ-панели только по `ADMIN_ID`
