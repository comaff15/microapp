# Микросервисный Task Manager

Учебный микросервисный проект для защиты в ВУЗе: управление проектами и задачами через веб‑интерфейс, авторизация и RBAC, ACL на уровне проекта (участники/роли), события через RabbitMQ, аудит и «уведомления» (логирование попыток доставки).

## Состав системы

- **gateway** (порт `8000`) — UI (FastAPI + Jinja2 + HTMX), прокси к API сервисам.
- **users** (порт `8001`) — регистрация/логин (JWT), `/users/me`, админские эндпоинты `/admin/users`.
- **tasks** (порт `8002`) — проекты/задачи, теги, архивирование, ACL по ролям (`owner/maintainer/viewer`), публикация событий.
- **audit** (порт `8003`) — потребитель событий, хранит неизменяемый audit log, `GET /events`.
- **notifier** (порт `8004`) — потребитель `task.*`, логирует «доставку уведомлений», `GET /notifications`.

Инфраструктура:
- **PostgreSQL** (данные)
- **RabbitMQ** (события)
- **Redis** (кэш tasks)

## Быстрый старт (Docker Compose)

### 1) Запуск сервисов

```bash
docker compose up --build -d
```

Открыть UI:
- `http://localhost:8000`

### 2) Учётка администратора

Админ создаётся при старте сервиса `users` (если отсутствует) из переменных окружения compose:
- `ADMIN_EMAIL=admin@local.ru`
- `ADMIN_PASSWORD=adminadmin`

## Основные URL

- gateway: `http://localhost:8000`
- users: `http://localhost:8001`
- tasks: `http://localhost:8002`
- audit: `http://localhost:8003`
- notifier: `http://localhost:8004`

## Тестирование (pytest / Playwright / Allure)

### Запуск тестов в контейнере

Тесты запускаются отдельным сервисом `tests` (профиль `tests`). Результаты Allure сохраняются на хост в папку `./allure-results`.

```bash
docker compose --profile tests up --build tests
```

Примечание:
- pytest настроен собирать тесты только из каталога `tests/`.

### Allure UI (визуализация результатов)

Allure UI читает данные из папки `./allure-results`, поэтому его можно поднять как **до**, так и **после** прогона тестов.

Поднять Allure сервис и UI:

```bash
docker compose --profile allure up -d allure allure-ui
```

Открыть Allure UI:
- `http://localhost:5252`

Allure API (Swagger):
- `http://localhost:5050`

Артефакты:
- `./allure-results` — сырые результаты
- `./allure-reports` — отчёты/история (генерируются сервисом Allure)

Минимальные сценарии:

1) Поднять приложение + Allure, тесты запускать отдельно:
```bash
docker compose --profile allure up --build -d
docker compose --profile tests up --build tests
```

## Нагрузочное тестирование (Locust)

Сценарии находятся в `perf/locustfile.py`.

Запуск Locust UI:

```bash
docker compose --profile perf up --build locust
```

Открыть:
- `http://localhost:8089`

Рекомендации по видам прогонов:
- **load**: 1–5 минут, небольшое число пользователей.
- **stress**: ramp-up до предела (пока не начнутся ошибки/деградация).
- **soak**: 30–60 минут с умеренной нагрузкой.

## Полезные команды

Остановить и удалить контейнеры:
```bash
docker compose down
```

Остановить и удалить контейнеры + тома (удалит данные Postgres):
```bash
docker compose down -v
```
