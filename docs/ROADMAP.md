# ROADMAP — этапы разработки

**Правило:** сроки не обещаются. Сложность указана относительно, а не в днях.
Каждый этап заканчивается проверяемым артефактом и тестами.

**Текущая версия приложения:** `v1.1.1`. Это чистый baseline
репозитория `cs2mb-tool`; исторические release notes сохранены как архив.

## Patch: v1.1.1 correctness and release maintenance — 2026-11-24

- Consolidated pipeline hardening, independent 3DsVW bounds and per-primitive
  glTF summary correctness.
- Made sidecar URI sanitization host-independent and replaced SRI reflection
  JSON serialization with source-generated metadata.
- Rebuilt and revalidated the Windows x64 package; SRI and 3DsVW versions remain
  unchanged.

## Milestone: v1.1.0 UI and 3DsVW — current 2026-11-24

- Redesigned the application workspace and settings while preserving intake,
  upload, job polling, library and comparison behaviour.
- Added **3DsVW — 3D Source Map Viewer** with locally bundled three.js, collision
  / NAV / entity / route layers, camera presets, selection metadata and embedded
  plus separate-tab modes.
- Added viewer-specific path confinement, glTF sanitization, size/triangle caps
  and endpoint tests.
- Added English and Russian user guides, current screenshots and v1.1.0 website
  and release updates.
- Release gate: clean package extraction, launcher, SRI, Dust2/Anubis viewer,
  docs access, checksums and SBOM.

## Historical: SRI and complete v1.0.0-pre.1 release — 2026-11-23

- Renamed the internal component to **SRI — Source Resource Inspector**.
- Closed P1 security backlog items: bounded jobs, process-tree timeout, endpoint
  tests, Host/Origin controls, disabled remote binding, upload cleanup and
  manifest path redaction.
- Rebuilt visual identity around the owner's original `logo.png`; removed
  invented logo variants; rebuilt technical illustrations and captured actual
  current application screenshots.
- Added a complete Windows package with SRI, portable Python 3.13, launchers,
  checksums and SPDX SBOM.
- Published and verified: complete package, GitHub pre-release, checksums,
  SPDX SBOM and Pages deployment; the old standalone engine release and tag
  were removed.

## Historical: internal Source 2 engine — completed 2026-11-23

**Status:** implemented and locally validated.

- First-party `cs2mb-sri` component built from `sri/`; VRF library
  linked in-process; self-contained Windows x64 artifact.
- PHYS and EntityLump decoded without Source2Viewer-CLI or `resourceinfo.exe`.
- Runtime CLI resolution removed from `tools/prepare_map.py` and
  `app/server.py`; legacy upload mode preserved.
- All nine active-duty maps converted; floor agreement 97.34–99.54%; Dust2
  historical totals reproduced exactly.
- 76 tests discovered (75 executed, 1 real-map test gated), engine CLI synthetic
  failure tests included, CI builds the engine on Windows.

**Next:** publish the versioned engine release asset with SHA-256, finish the
README/site/logo/social-preview presentation, and keep the coordinate/format
validation current when CS2 or ValveResourceFormat changes.

## Обозначения

- **Core** — обязательное ядро.
- **Extension** — полезное расширение.
- **Research** — исследовательская функция; может не войти в продукт.
- **S/M/L** — относительная сложность.

## Этап 0. Исследование и инвентаризация данных

**Статус:** выполнен.

**Цель:** доказать, что реальные ресурсы установленной CS2 содержат nav,
entities и collision, и что их можно читать.

**Результат:**

- подтверждён путь к игре и версия;
- найден `.nav` в map VPK;
- написан read-only VPK/nav loader;
- разобраны 2242 области Dust2;
- найдены 15 T / 15 CT spawns и 43 callout;
- подтверждён `world_physics.vmdl_c` с PHYS block;
- получены weapon max speeds;
- написаны docs.

**Критерий приёмки:** nav parser читает все официальные nav без выхода за
границы файла; эксперимент на Dust2 воспроизводим.

**Риски:** версия игры; скрытые особенности формата; `Test-Path` в Windows.

**Зависимости:** нет.

## Этап 1. Воспроизводимый importer и Map Bundle

**Класс:** Core, M.

**Цель:** превратить установленную игру в версионированный bundle, не
зависящий от game runtime.

**Результат:**

- CLI-wrapper с pinned Source2Viewer (20.1) и проверкой версии;
- `manifest.json` с build, hashes, tool versions;
- `nav.json`, `entities.json`, `collision.glb`, `collision_meta.json`;
- `radar.png` + `overview.json` (опционально);
- temp/working directories, никаких записей в игру;
- повторный запуск даёт те же хэши (кроме timestamp).

**Источники:** `game/csgo/maps/<map>.vpk`, `pak01_dir.vpk`,
`game/csgo/steam.inf`.

**Инструменты:** Source2Viewer-CLI, наш VPK reader (только research),
`resourceinfo.exe` (fallback).

**Алгоритмы:** VPK index, resource header, entity dump, glTF import.

**Критерии приёмки:**

- [ ] Dust2 bundle собирается одной командой.
- [ ] `nav.json` проходит golden.
- [ ] `collision.glb` содержит > 0 треугольников и PHYS-derived metadata.
- [ ] manifest позволяет отличить версию игры.
- [ ] Ни один файл игры не изменён.

**Тесты:**

- unit: manifest schema, hash;
- integration: VPK → bundle;
- negative: vanity/preview map отвергается;
- reproducibility: два запуска.

**Риски:** CLI меняет аргументы; экспорт тяжёлый; collision filters.

**Зависимости:** согласование на скачивание/распаковку CLI.

## Этап 2. Nav graph и маршрутизация

**Класс:** Core, M.

**Цель:** стабильный граф и маршруты без game runtime.

**Результат:**

- `NavGraph` loader;
- point location (XY + z);
- directed edges, edge crossings, line-graph Dijkstra;
- components/SCC/one-way/vertical diagnostics;
- route result: area ids, points, distance, diagnostics;
- SVG визуализация;
- cross-check с Awpy.

**Источники:** `nav.json`.

**Инструменты:** Python stdlib; Awpy для сравнения (после установки).

**Алгоритмы:** point-in-polygon, Dijkstra, Kosaraju, edge midpoint,
line-graph shortest path, k-shortest (extension).

**Критерии приёмки:**

- [ ] Dust2 2242 areas, 6275 edges, ожидаемые counts.
- [ ] 15/15 spawn → area.
- [ ] T/CT → Mid/A/B маршруты.
- [ ] route length ≥ straight line.
- [ ] forward/reverse объяснены.
- [ ] SVG routes визуально валидны.

**Тесты:** synthetic fixture, golden counts, bounds, edge semantics,
cross-parser.

**Риски:** one-way/edge semantics; ladders; floating point.

**Зависимости:** этап 1 (или raw nav для research).

## Этап 3. Collision geometry и проходимость

**Класс:** Core, L.

**Цель:** проверить nav-маршруты по реальной collision и получить
floor/clearance/LOS.

**Результат:**

- загрузка `world_physics` glTF;
- фильтрация material groups (walkable/blocking/playerclip/sky/glass);
- BVH;
- floor sampling;
- segment blocked;
- capsule clearance (radius 16, height 71; crouch 35.5);
- nav↔collision diagnostics;
- overlay nav + collision + routes.

**Источники:** `world_physics.vmdl_c`, material names, nav.

**Инструменты:** Source2Viewer CLI, NumPy/SciPy или C#/Rust при
необходимости.

**Алгоритмы:** triangle mesh, BVH, ray-triangle, distance, capsule
intersection, spatial index.

**Критерии приёмки:**

- [ ] Dust2 collision загружается.
- [ ] 95%+ случайных nav-точек имеют floor в пределах tolerance.
- [ ] Подозрительные nav-связи проверены.
- [ ] Нет маршрутов, проходящих сквозь явную стену, без флага.
- [ ] Производительность: интерактивный запрос < 100 мс на cache.

**Тесты:** floor test, wall test, clearance test, synthetic box map,
сравнение с Awpy visibility (если доступно).

**Риски:** 21.8/61 МБ collision; фильтрация материалов; static props;
dynamic doors; coordinate transform.

**Зависимости:** этап 1; согласование CLI.

## Этап 4. Модель движения

**Класс:** Core, L.

**Цель:** превратить расстояния во время с измеренной неопределённостью.

**Результат:**

- `movement_profile.json`;
- weapon speed table из `weapons.vdata_c`;
- acceleration/friction/stop speed;
- crouch/walk/zoom;
- jump/drop/ladder;
- travel time calculator;
- validation report.

**Источники:** `scripts/weapons.vdata_c`, competitive cfg, локальные
измерения в CS2.

**Инструменты:** локальный сервер CS2 (после согласования), demo/`cl_showpos`,
Python fit.

**Алгоритмы:** кинематика, fit параметров, Monte Carlo для неопределённости.

**Критерии приёмки:**

- [ ] Все ключевые оружия имеют max speed.
- [ ] Прямолинейный тест: ошибка < 5–10%.
- [ ] Повторяемость: stdev < 5%.
- [ ] Crouch/walk/zoom проверены.
- [ ] Параметры и разброс записаны.

**Тесты:** straight-line speed, accel/decel, jump, ladder, regression
profile.

**Риски:** изменения CS2; поверхность/рампы; оружие/зум; tickrate;
невозможность точного автоматического замера.

**Зависимости:** этап 2; разрешение на запуск CS2.

## Этап 5. Симуляция 5v5 (движение, без боя)

**Класс:** Core/Extension, L.

**Цель:** распределение времени прибытия и конфликты маршрутов.

**Результат:**

- 5 T + 5 CT;
- spawn assignment (детерминированный + вероятностный режим);
- route choice;
- travel times;
- meeting points/bottlenecks;
- seed, reproducibility;
- JSON/CSV output.

**Источники:** bundle, movement profile, scenario config.

**Инструменты:** Python; NumPy для Monte Carlo (опционально).

**Алгоритмы:** multi-agent routing, discrete-time simulation, queue/occupancy,
k-shortest, sensitivity.

**Критерии приёмки:**

- [ ] 10 агентов, 5/5.
- [ ] Нет телепортов/отрицательного времени.
- [ ] 1000 запусков сходятся по медиане.
- [ ] Bottlenecks воспроизводятся.
- [ ] Все параметры заданы externally.

**Тесты:** invariants, seed, convergence, blocked route, spawn assignment.

**Риски:** поведенческая неопределённость; очередь; unrealistic route choice.

**Зависимости:** этапы 2–4.

## Этап 6. Метрики баланса и чувствительность

**Класс:** Core, M.

**Цель:** проверяемые метрики без единственного «balance score».

**Результат:**

- time-to-point distributions;
- side differences;
- spawn spread;
- alternative route availability;
- bottleneck indicators;
- sensitivity to speed/spawn/route;
- bootstrap CI;
- отчёт.

**Источники:** результаты этапов 2–5.

**Инструменты:** Python/NumPy, SVG/plots.

**Алгоритмы:** bootstrap, sensitivity, scenario comparison.

**Критерии приёмки:**

- [ ] Метрики имеют распределение/CI.
- [ ] Вывод устойчив к ±10% скорости или явно помечен как чувствительный.
- [ ] Нет вывода «карта сбалансирована» по одному числу.
- [ ] Все допущения перечислены.

**Тесты:** synthetic known-answer, sensitivity, regression.

**Риски:** ложная точность; overfitting к Dust2; неверное назначение спавнов.

**Зависимости:** этапы 2–5.

## Этап 7. Визуализация и отладка

**Класс:** Extension, M.

**Цель:** быстро видеть nav, маршруты, аномалии, collision overlay.

**Результат:**

- SVG/PNG карты;
- color by z/component/flag;
- routes/alternatives;
- one-way/anomaly markers;
- heatmaps;
- 3D collision navigation mesh overlay (позже).

**Инструменты:** SVG stdlib → matplotlib/PyVista/Potree.

**Критерии:** визуализация воспроизводит те же area IDs/маршруты, что JSON.

**Риски:** большие данные; 3D-зависимости; визуальная перегрузка.

**Зависимости:** этапы 1–3.

## Этап 8. Multi-map и регрессия

**Класс:** Extension, M.

**Цель:** поддержка competitive map pool и обновлений.

**Результат:**

- map registry;
- batch ingest;
- cross-map diagnostics;
- regression dashboard;
- version pinning.

**Критерии:** все целевые карты проходят baseline; обновление игры создаёт
diff, а не молчаливое изменение.

**Риски:** разные nav generation params; ladders; multi-level maps; размер
collision.

**Зависимости:** этапы 1–6.

## Этап 9. Тактические расширения (Research)

**Класс:** Research, XL.

**Возможные функции:**

- visibility/field-of-view;
- smoke/molotov/utility zones;
- bomb plant/defuse timing;
- economy;
- combat model;
- learning-based behavior.

**Критерии:** только после валидации базовой геометрии и движения; иначе
получим красивый, но недостоверный симулятор.

**Риски:** комбинаторный взрыв; отсутствие данных; ложная точность.

## Ручная коррекция спавнов (Extension, низкий приоритет)

**Проблема:** автоматическое определение спавна может выбрать неверную
область/этаж, особенно на multi-level картах или после нестандартного
spawn-ассортимента.

**Функция:**

- в UI или отдельном JSON можно переопределить spawn:
  - side;
  - индекс/имя spawn point;
  - origin;
  - area_id;
  - необязательный комментарий;
- override хранится в `config/spawn_overrides/<map>.json` и не изменяет
  исходные ресурсы игры;
- загрузчик применяет override после auto-detect;
- невалидный origin/area отклоняется с объяснением;
- в UI такой spawn помечается другим цветом/бейджем;
- simulation использует override, а отчёт фиксирует, что это ручная правка.

**Критерии приёмки:**

- override загружается и воспроизводится;
- auto-detect остаётся значением по умолчанию;
- неверный area_id отклоняется;
- тест: auto vs override;
- исходные nav/entities не изменяются.

**Зависимости:** стабильные nav/entities и UI; не входит в MVP.

**Сложность:** M.

**Статус:** backlog, не приоритет.

## Auto-generation pipeline (future)

**Видение:** пользователь даёт файлы карты (или путь к установленной CS2),
нажимает `Generate` — программа сама собирает данные, считает все полезные
маршруты обеих сторон, показывает их динамическое появление и времена
обнаружения/встреч.

**Уже есть:** `tools/auto_generate.py` принимает `.nav`, entity dump и
physics glTF, запускает floor/wall/clearance checks, собирает viewer, summary
и `manifest.json`; локальное `app/server.py` + `app/index.html` дают browser
upload/drop, `Generate`, job log, viewer и map library; viewer строит все
spawn→target routes с анимацией (Dust2 — 90).

**Следующие слои:**

1. Автоматическое извлечение nav/entities/collision из VPK/VRF (без ручных
   temp-путей).
2. Генерация alternatives/K-shortest, не только одного пути на spawn→target.
3. Detection/encounter times (Release 2.2).
4. Прогресс/отмена и более удобная library comparison.
5. Combat (Release 2.3) - только после demo-калибровки.

**Критерий:** один и тот же вход + seed даёт одинаковый manifest/результат.
UI не должен блокироваться на время тяжёлого расчёта.

**Статус:** Release 2.1 local done; auto extraction from installed CS2,
upload/drop, verdict, compare + security hardening.

## Приоритеты

### Обязательное ядро

1. Этап 1 — bundle.
2. Этап 2 — nav graph/routes.
3. Этап 3 — collision floor/wall/clearance.
4. Этап 4 — движение.
5. Этап 5 — простая 5v5 симуляция времени.
6. Этап 6 — метрики с CI.

### Полезные расширения

- альтернативные маршруты;
- ручная коррекция спавнов (см. раздел выше);
- визуализация 3D;
- multi-map;
- batch regression.

### Исследовательские функции

- visibility;
- utility;
- combat;
- RL.

## Минимальный первый прототип

**Сделать в первую очередь:**

1. `de_dust2` bundle.
2. Nav graph + 15 spawn → Mid/A/B.
3. SVG.
4. Diagnostics.
5. Один collision floor test.
6. Отчёт с расстояниями, без времени.

Это уже частично сделано в research-скриптах; production-версия должна
переехать в модули и получить тесты.

## Зависимости между этапами

```text
0 ─► 1 ─► 2 ─► 3 ─► 6
          │     │
          └─► 4 ─► 5 ─► 6
                      │
                      └─► 7
1 ───────────────────► 8
2+3+4 ───────────────► 9
```

## Текущий прогресс

- Этап 0 — выполнен.
- Этап 2 (nav graph/routes) — research-версия выполнена на Dust2.
- Этап 7 (визуализация) — HTML/SVG UI-прототип выполнен и переработан в
  Source 2-style shell с beginner quick start, route cards, validation
  card, белыми collision-линиями стен и 90 spawn→target routes с анимацией
  (`prototype/dust2_viewer.py`, `prototype/ui_template.html`); это не
  production-визуализация.
- Этап 1 (полный importer/bundle) — не завершён.
- Этап 3 (collision) — PHYS export через VRF выполнен (435 649 triangles),
  floor test 98.77% ≤16 u; wall test 6091 connections, 2 blocked playerclip;
  point-sample clearance 8812 samples (21 low ceiling, 1 narrow); 6 floor
  anomalies разобраны; swept-capsule probe 6091 connections, 516 flags
  (triage); LOS — нет.
- Multi-level — `find_area_verbose`/`vertical_layers` и synthetic test
  выполнены; на Nuke/Vertigo/Train проверены stacked XY layers.
- Этап 4 (movement) — convars и steady-state скорости измерены; модель
  `movement/source.py` воспроизводит AK/knife/AWP/walk/crouch.
  `movement/route.py` считает vertical transitions/turns, диапазон
  continuous → stop-at-crossings и отдельный `J+` jump budget; CT→A median
  имеет `↑6`, `J+3.0`, `+272/-49`, `AK 6.5–10.0 s`. Jump/turn/landing
  не откалиброваны по demo ticks.
- Этап 5 (5v5 time-only) — partial: `simulation/scenario.py`; 5-man rush
  envelope (exact `C(15,5)`) и split 2 A / 2 B / 1 Mid с optimal/random/
  softmax assignment. Калибровка policy, blocking/combat и demo-проверка
  не начаты.
- Auto-generation — local app `app/server.py` + `app/index.html`: browser
  upload/drop, Generate, job → viewer, summary/library; CLI
  `tools/auto_generate.py` (Dust2 full 152 s / skip clearance 19.3 s);
  viewer строит 90 animated routes. Detection/encounter и combat не начаты.
- Этапы 6, 8–9 — не начаты.

## Release 2.1 - Map Generation & Comparison

**Статус: done (local), security-hardened.**

- **Prepare + Generate from installed CS2**: автоматическое извлечение
  nav/entities/collision внутри программы;
- upload/drop fallback, first-run tutorial, stepper, manifests, all routes;
- **time-only verdict**: balanced / CT advantage / T advantage;
- **Compare selected** в map library;
- сравнение: areas/edges/floor/wall/clearance и CT→A/T→A median low;
- route cards требуют стандартные `BombsiteA/B/Middle` callouts;
- без detection/encounter, combat и dynamic analysis.

Acceptance: `docs/RELEASE.md`.

## Release 2.2 - Detection / Encounter

**Статус: next.**

- LOS по collision;
- время возможного обнаружения двух агентов на маршрутах;
- encounter windows и первые точки контакта;
- seed/воспроизводимость;
- всё ещё без combat/damage.

## Release 2.3 - Combat

**Статус: later.**

- только после demo-калибровки movement + detection;
- duel/encounter model, не «предсказание победителя» без данных.

## Release 3.0 — Internal Source 2 resource pipeline (research)

**Статус: research/backlog.** Не блокирует 2.2/2.3; можно начинать
format-research параллельно, но не заменять рабочий pipeline до прохождения
golden-тестов.

**Цель:** убрать обязательную зависимость от внешних `resourceinfo.exe` и
Source2Viewer-CLI из основного runtime-пути. Свои парсеры должны давать те же
nav/entity/collision данные, что и текущая связка, но без ручного экспорта.

**Что уже наше:**

- VPK reader и provenance;
- nav parser, area graph, routes;
- entity points parser для уже снятого `entities.txt`;
- glTF collision index, floor/wall/clearance/BVH;
- viewer, summary, manifest.

**Что нужно заменить:**

1. **Entity lump** — читать `default_ents.vents_c` напрямую и извлекать
   spawns/bombsites/callouts/buyzones; golden-сравнение с текущим
   `resourceinfo` dump.
2. **Physics collision** — читать Source 2 physics/VMDL-данные напрямую и
   строить треугольники/BVH так же, как сейчас из `world_physics_physics.gltf`;
   golden-сравнение с Source2Viewer export. Материалы и render-меши не нужны.
3. **Fallback** — при неизвестной версии/битом формате использовать текущий
   внешний путь; внутренний парсер не должен ломать уже работающие карты.

**Этапы:**

- **3.0a format census:** подтвердить структуры, версии, coordinate transforms,
  собрать synthetic fixtures и эталонные hashes; ничего не менять в runtime.
- **3.0b entity parser:** внутренний entity dump; сравнение counts/positions
  с `resourceinfo` на 9 картах.
- **3.0c physics parser:** внутренний collision export; сравнение triangles,
  bounds, floor/wall/clearance с Source2Viewer.
- **3.0d switch:** убрать внешние инструменты из default UI; оставить их как
  validation oracle и opt-in fallback.

**Критерии приёмки:**

- те же nav/route counts и representative routes;
- floor/wall/clearance без регрессии на golden-наборе;
- viewer открывается без console errors;
- manifest содержит версию парсера, source hash и provenance;
- нет запуска CS2, чтения памяти, сети или записи в игру;
- тесты на synthetic fixtures + 9 реальных карт.

**Почему это реально:** VPK/nav/geometry/viewer уже собственные; осталось
разобрать два бинарных слоя и сохранить текущую схему нормализации.
**Почему не сразу:** Source 2 форматы меняются между патчами; ошибка в PHYS/
entity парсинге даст ложную геометрию, поэтому нужен golden-oracle и fallback.

**Не делать:** полный Source 2 render/material parser, 3D-движок и замену
внешних инструментов «по ощущениям» без сравнения с эталоном.
