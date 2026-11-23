# RELEASE pre-alpha v1.0 — чистый baseline репозитория

**Версия приложения:** `pre-alpha v1.0`

Это исходный чистый baseline репозитория `cs2mb-tool`. Он сохраняет
документированный объём анализа 2.x, но меняет идентичность репозитория и
текущую версию.

## Что есть

- read-only intake карт CS2, NAV-парсер, entities и диагностика коллизий;
- локальный viewer, route/profile output и библиотека карт;
- time-only rush/split сценарии и сравнение времени маршрутов;
- локальный loopback server с контролем upload/path и таймаутом jobs;
- двуязычная документация и setup guides;
- текущее значение `VERSION`: `pre-alpha v1.0`.

## Ограничения

- нет detection/encounter timing, combat, utility и прогноза win rate;
- route-time — предварительная эвристика, а не вердикт о балансе матча;
- движение откалибровано по прямой и не проверено по demo ticks;
- исторические release notes 2.x в `docs/releases/` остаются архивом.

## Проверка

Текущая проверка включает 56 unit tests, компиляцию Python, repository hygiene
scan, проверку Markdown-ссылок/якорей/блоков и целостности assets. См.
[STATE.md](STATE.md).

## Исторические release notes

Release notes 2.x сохранены как исторические записи:
[releases/](releases/).

## Английская версия

[RELEASE.md](RELEASE.md).
