# CS2 Map Balance v1.1.0 — примечания к релизу

**Версия приложения:** `v1.1.0`
**Версия SRI:** `1.0.0`
**Версия 3DsVW:** `1.0.0`
**Тип:** обычный релиз, Windows x64

Этот релиз превращает CS2MB в полноценное desktop-ориентированное рабочее
пространство и добавляет **3DsVW — 3D Source Map Viewer**, read-only
пространственный вид на данных, которые уже производит pipeline.

## Интерфейс приложения

- Новые разделы: Обзор, Обработка, Библиотека, Viewer, Настройки.
- Прямоугольные панели, компактная типографика, холодный cyan/blue акцент.
- Только локальные SVG-иконки; без emoji и без CDN.
- Повторяющиеся обучающие абзацы убраны из рабочего процесса; остались
  контекстная помощь и отдельное руководство.
- Последние карты, ссылки на документацию и понятный статус на обзоре.

## 3DsVW

- WebGL2 viewer с локально упакованным three.js `0.160.0`.
- Показывает collision из SRI PHYS, NAV-полигоны/связи, entity-маркеры и
  представительные маршруты.
- Полы, стены, прочие collision-поверхности и clip/sky разделены.
- Orbit, pan, zoom, fit, top, isometric и reset камеры.
- Независимые слои collision/NAV/entity/route.
- Инспектор показывает только доступные метаданные: node, category, surface,
  collision group, `InteractAs`, material, hit point, NAV area или entity.
- Встроенный режим и отдельная вкладка используют одну реализацию.
- Без CDN, внешних текстур и runtime-загрузок.
- Рендер по требованию, frustum culling и группировка draw calls.

## Настройки

- Режим viewer по умолчанию: 3DsVW или 2D.
- Качество 3D: Performance, Balanced, Quality (pixel ratio).
- Слои 3DsVW по умолчанию, включая clips/sky и NAV links.
- Запоминание настроек и сброс к значениям по умолчанию.
- Настройки сохраняются локально и применяются к встроенному и отдельному viewer.

## Документация

- Новые руководства на английском и русском.
- Описаны установка, SRI, 2D viewer, 3DsVW, настройки, troubleshooting,
  приватность и ограничения.
- Новые скриншоты заменяют старые снимки v1.0.
- Обновлены сайт, README, social preview и Pages workflow.

## Безопасность и производительность

- Viewer принимает только сгенерированные bundles внутри ограниченных
  map/job-путей.
- Неверные map/job ID, traversal и отсутствующие файлы возвращают 404.
- glTF нормализуется: заполняется `bufferViews[].buffer`, удаляются текстуры и
  изображения, внешние buffer URI отклоняются.
- Входы viewer ограничены размером glTF, sidecar, числом nodes/accessors и
  четырьмя миллионами collision-треугольников.
- CSP viewer: `script-src 'self'`, `connect-src 'self'`,
  `frame-ancestors 'self'`; приложение может встраивать viewer, внешние origin —
  нет.
- Метаданные выводятся через безопасные текстовые DOM API.
- Сохранены loopback-only, Host/Origin checks, upload limits, job limits и
  process-tree timeout.
- 3DsVW рендерит по требованию и приостанавливается в скрытой вкладке.

## Измеренные локальные данные

| Карта | Collision triangles | NAV areas | Draw calls |
|---|---:|---:|---:|
| de_dust2 | 435,649 | 2,242 | 164 |
| de_anubis | 715,842 | 2,633 | 141 |

Draw calls — локальный замер в Edge на референсном ПК, не универсальный
benchmark. Основной объём данных — collision glTF/bin; 3DsVW копирует
нормализованную версию в bundle задачи.

## Проверка

- Python suite, security scan, compileall, JavaScript syntax, SVG XML и проверка
  ссылок.
- Тесты builder 3DsVW на синтетических NAV/glTF и отклонение внешнего buffer.
- Endpoint-тесты viewer: traversal, неверные ID, отсутствующие bundles, CSP,
  confined paths.
- Автоматическая подготовка Dust2 и Anubis и upload-режим.
- Загрузка embedded и separate-tab viewer на реальных данных.
- Распаковка пакета, SRI, launcher, доступ к документации и checksums.

## Совместимость и ограничения

- Windows 10/11 x64.
- Портативный Python 3.13 включён.
- Для 3DsVW нужен WebGL2.
- SRI только Windows x64 и не подписан code-signing сертификатом.
- 3DsVW — collision-derived технический вид, не render-геометрия, материалы или
  текстуры игры.
- Нет редактирования карты, box selection и измерительных инструментов.
- Кривые collision-примитивы тесселируются приближённо.
- Route time — оценка, не баланс матча.
- Валидация привязана к записанной сборке CS2; будущие изменения Valve могут
  потребовать обновления SRI.

## История

Полный пакет v1.0.0-pre.1, переименование в SRI и предыдущая валидация остаются
в [releases/](releases/) и changelog.
