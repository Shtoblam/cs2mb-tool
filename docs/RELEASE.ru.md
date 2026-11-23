# CS2 Map Balance v1.0.0-pre.1 — полный pre-release

**Версия приложения:** `v1.0.0-pre.1`
**Версия SRI:** `1.0.0`
**Тип:** pre-release, Windows x64

Первый полный дистрибутив CS2MB. Включает приложение, собственный **SRI —
Source Resource Inspector**, портативный Python 3.13 runtime, launchers,
документацию, checksums и SPDX SBOM.

## Обработка Source 2

- Внутренний компонент переименован в SRI — Source Resource Inspector.
- SRI разбирает скомпилированные PHYS и EntityLump с закреплённой MIT
  библиотекой ValveResourceFormat `20.1.7467`.
- Source2Viewer-CLI и `resourceinfo.exe` больше не являются runtime-зависимостями.
- Координаты остаются в Hammer units и Source axes (`x`, `y`, `z-up`);
  устаревшая glTF node matrix не применяется.
- Mesh и convex-hull геометрия точная; sphere/capsule используют bounded
  tessellation.
- Сохраняются `InteractAs`, `SurfaceProperty` и `CollisionGroup`.
- Путь, версия и SHA-256 SRI записываются в preparation manifests.

## Приложение

- Один полный Windows-пакет с `Start-CS2MB.bat` и `Start-CS2MB.ps1`.
- Портативный Python 3.13 runtime; установка Python и `pip` не нужны.
- Определение SRI и отображение версии в приложении.
- Существующие NAV, routing, collision, movement, simulation, viewer и library
  сохранены.
- Ручная загрузка `.nav`, entity `.txt`, `.gltf` и `.bin` остаётся.

## Визуальная идентичность

- Оригинальный `logo.png` восстановлен байт-в-байт как канонический знак.
- Удалены выдуманные векторные варианты логотипа.
- Перестроены banners, SRI/pipeline схемы, navigation, collision и security
  иллюстрации в сдержанной charcoal/crimson системе.
- Social preview 1280×640 построен вокруг оригинального логотипа.
- Ассеты организованы в `brand/`, `banners/`, `illustrations/`, `screenshots/`.
- Сделаны реальные скриншоты текущего приложения, viewer, library и onboarding.

## Безопасность

- Не более двух одновременных jobs; лишние получают HTTP 429.
- Старые job records и upload directories очищаются.
- Windows timeout завершает полное дерево процессов, включая SRI.
- Loopback Host allow-list и same-origin POST checks; POST без Origin отклоняется.
- Remote binding (`--allow-remote`) отклоняется.
- Отклонённые uploads удаляются.
- Preparation manifests не содержат личных абсолютных путей.
- Endpoint-тесты покрывают oversized uploads, malformed multipart, traversal,
  extensions, missing sidecars, invalid JSON, viewer confinement, Host/Origin и
  job limits.
- GitHub Actions закреплены на immutable commit SHA.
- Release содержит `SHA256SUMS.txt` и `SBOM.spdx.json`.
- SRI не подписан code-signing сертификатом; hashes — проверка целостности, не
  подпись.

## Совместимость

- Windows 10/11 x64.
- Портативный Python 3.13 входит в полный пакет.
- Локальная CS2 необязательна для авто-извлечения.
- Проверено на CS2 build `2000948` (2026-11-19).
- Upload-режим работает без CS2 и SRI.

## Известные ограничения

- SRI только Windows x64.
- Кривые collision-примитивы тесселируются приближённо.
- Полный clearance проверялся на Dust2 и Nuke; остальные карты использовали
  `Skip clearance`.
- Поддержка entity/PHYS привязана к записанной сборке CS2; будущее изменение
  формата может потребовать обновления SRI.
- Movement-модель остаётся straight-line и не включает combat, utility,
  visibility или решения игроков.
- Viewer HTML generation не является browser sandbox; оставшиеся работы по
  viewer-content и code-signing — в `docs/SECURITY_BACKLOG.md`.
- Route-time индикатор — предварительная эвристика, не вердикт баланса.

## Проверка

- 88 tests discovered / 87 executed / 1 real-map test gated через `CS2MB_TEST_GAME`.
- SRI Release build и engine-backed тесты.
- Локальная интеграционная валидация девяти карт.
- Python compilation, repository hygiene scan, Markdown, SVG/XML и asset refs.
- Package extraction, launcher, SRI detection и HTTP startup.
- Checksums пересчитаны из опубликованного архива.

## История релизов

Ранние 2.x notes остаются в [releases/](releases/). Старый standalone
`source2-v1.0.0` удаляется после проверки полного релиза.
