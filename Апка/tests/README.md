# Тесты

## Запуск

- Приложение:
  - docker compose up --build -d

- Тесты (контейнер `tests`, профиль `tests`):
  - docker compose --profile tests up --build tests

## Allure (UI)

- API (Swagger):
  - http://localhost:5050
- UI:
  - http://localhost:5252

Поднять Allure сервисы:

- docker compose --profile allure up -d allure allure-ui

## Запуск тестов без интернета

Идея простая: один раз (когда интернет есть) заранее собрать/скачать всё необходимое, а потом оффлайн запускать тесты без пересборки.

### 1) Подготовка один раз (когда интернет есть)

Скачать образы:

- docker compose pull
- docker compose --profile allure pull
- docker compose --profile perf pull

Собрать локальные образы проекта (включая `tests`):

- docker compose build
- docker compose --profile tests build tests

Примечание: образ `tests` при сборке устанавливает зависимости Python и Playwright Chromium, это требует интернета на этапе подготовки.

### 2) Оффлайн запуск

Поднять приложение (без `--build`):

- docker compose up -d

Прогнать тесты (без `--build`):

- docker compose --profile tests run --rm --no-deps tests

`--no-deps` полезен, если приложение уже поднято отдельной командой `up -d`.

### 3) Allure оффлайн

Если образы уже скачаны, Allure UI и API поднимаются оффлайн:

- docker compose --profile allure up -d allure allure-ui

### 4) Частые причины проблем оффлайн

- Не запускай тесты с `--build` — это может триггерить скачивание зависимостей.
- Если каких-то образов нет локально, Docker попытается их скачать.

## Слои (pytest markers)

- unit
- api
- integration
- data
- e2e
- contract
- security
