# ARCHITECTURE — рекомендуемая архитектура и технологический стек

**Статус:** актуальная архитектурная справка. Часть разделов описывает исходный
план и помечена как предложение; фактический статус модулей указан в тексте и
в [STATE.md](STATE.md). Документ не является обещанием, что все описанные
модули уже реализованы.

## 1. Принципы

1. **Игра — источник, но не runtime-зависимость.** Все игровые ресурсы
   импортируются один раз в воспроизводимый bundle; анализ работает без CS2.
2. **Один bundle — одна версия карты.** Manifest содержит build, хэши и версии
   инструментов. Несовпадение версий — ошибка, а не предупреждение.
3. **Nav и collision — разные слои.** Нельзя «доставать» коллизию из nav и
   наоборот.
4. **Сначала измеримое.** Время не появляется, пока не измерена модель
   движения. Баланс не появляется, пока нет распределения и неопределённости.
5. **Минимум зависимостей.** Python stdlib для графа и метрик; Source2Viewer
   CLI — единственный тяжёлый внешний инструмент на этапе импорта.
6. **Всё проверяемо.** Каждый модуль имеет вход, выход, критерии корректности и
   тест, не требующий запуска CS2.

## 2. Поток данных

```text
CS2 install (read-only)
   │
   ├─ map VPK ──► nav bytes ───────────────┐
   │              entities (.vents_c) ─────┤
   │              world_physics.vmdl_c ────┤
   │              world/render (optional) ─┤
   │                                       │
   └─ pak01 ────► weapons.vdata_c, cfg ────┤
                                           ▼
                              [INGEST] Source2Viewer-CLI / resourceinfo
                                           │
                                           ▼
                              [NORMALIZE] coordinates, IDs, units
                                           │
                                           ▼
                    Map Bundle (immutable, versioned, local)
                    ├─ manifest.json
                    ├─ nav.json
                    ├─ entities.json
                    ├─ collision.glb / collision.npz
                    ├─ visual.glb (optional)
                    ├─ radar.png + overview.json (optional)
                    └─ metrics/*.json
                                           │
              ┌────────────────────────────┼────────────────────────────┐
              ▼                            ▼                            ▼
        [NAV GRAPH]                  [COLLISION]                  [MOVEMENT]
        areas, routes                BVH, clearance               speeds, accel
              │                            │                            │
              └──────────────┬─────────────┴──────────────┬─────────────┘
                             ▼                            ▼
                     [SIMULATION]                  [BALANCE]
                     5v5, timing                   metrics, sensitivity
                             │                            │
                             └────────────► [VIZ] ◄──────┘
                                           SVG / 2D / 3D
```

## 3. Технологический стек

### 3.1. Рекомендуемый минимум

| Слой | Технология | Почему |
|---|---|---|
| Оркестрация | Python 3.13 | Быстрая разработка, stdlib, удобные тесты |
| Импорт VPK/ресурсов | Source2Viewer-CLI (pinned) | Уже покрывает VPK, vmap/vmdl/vents/PHYS, glTF |
| Nav loader | Python (наш `nav_inspect` → production-модуль) | Контроль над edge semantics, ladders, generation params |
| Граф | Python stdlib (`heapq`, `collections`) | 2–4 тыс. областей; не нужен NetworkX для MVP |
| Геометрия | Python stdlib + `array`/grid index (фактически) | Треугольники, floor/segment checks; BVH и NumPy/SciPy — только при доказанной необходимости |
| Визуализация | SVG (stdlib) → matplotlib/PyVista при необходимости | Дешёвый старт; 3D — позже |
| Тесты | `unittest` + synthetic fixtures (фактически); golden JSON — план | Стандарт библиотеки; property-based — по желанию |
| Хранение | JSON + Parquet/SQLite | Прозрачность; без БД-сервера |
| Git | локальный + GitHub origin | Репозиторий опубликован; remote настроен |

### 3.2. Альтернативы

| Вариант | Плюсы | Минусы | Когда выбирать |
|---|---|---|---|
| C# + VRF library | Прямой in-process доступ ко всем ресурсам, скорость | Меньше исследовательских библиотек; дольше итерации | Если импорт станет bottleneck или нужен единый .NET-продукт |
| Rust + cs2-nav | Скорость, готовый nav/visibility | Высокая стоимость разработки; нужен `.tri` | Если нужен production-сервис с жёсткими latency-требованиями |
| Python + Awpy | Готовый nav/demo parsing | Меньше контроля над edge/ladders; внешние ассеты | Для cross-check и demo-валидации |
| Полный собственный Source 2 parser | Полный контроль | Огромная стоимость, ошибки, поддержка форматов | Не рекомендуется; только узкий nav/VPK loader |

**[INFERENCE]** Для исследования и MVP Python + Source2Viewer-CLI — лучший
баланс. Переход на C#/Rust оправдан только после профилирования.

## 4. Модули и границы

### 4.1. `ingest`

**Вход:** путь к установленной CS2, имя карты, версия инструмента.
**Выход:** raw-файлы в temp + `manifest.json`.
**Обязанности:**

- найти map VPK, проверить версию и хэши;
- извлечь `.nav`, `default_ents.vents_c`, `world_physics.vmdl_c`;
- вызвать Source2Viewer-CLI для glTF/entity dump;
- проверить, что nav area_count > 0 и версия поддерживается;
- не писать в каталог игры.

**Запрещено:** читать игру во время анализа; молча обновлять версию.

### 4.2. `normalize`

**Вход:** raw + manifest.
**Выход:** Map Bundle.
**Обязанности:**

- привести ID к стабильным ключам;
- проверить координатную систему (Hammer units, Z-up);
- спроецировать spawn/callout XY на nav;
- сохранить исходные координаты и transformed;
- проверить, что все обязательные сущности найдены;
- записать provenance (source path, hash, tool version).

**Граница:** нормализация не знает о маршрутах и симуляции.

### 4.3. `navgraph`

**Вход:** `nav.json`.
**Выход:** `NavGraph`, `PathResult`, `NavDiagnostics`.
**Обязанности:**

- area lookup по точке (XY + высота);
- directed edges, edge IDs, crossing points;
- SCC, components, one-way, dangling, vertical anomalies;
- line-graph Dijkstra;
- альтернативные маршруты (k-shortest / penalization) — расширение;
- ladders как отдельный тип перехода.

**Граница:** не читает collision и не считает время.

### 4.4. `collision`

**Вход:** `collision.glb`/triangles + metadata.
**Выход:** BVH, `is_visible`, `raycast`, `floor_at`, `clearance`, `segment_blocked`.
**Обязанности:**

- загрузить треугольники и material groups;
- отделить walkable/blocking/clip/sky/glass;
- BVH;
- проверка nav-перехода: есть ли стена между crossing points;
- проверка пола под точкой;
- оценка ширины прохода (позже).

**Граница:** не строит маршруты; получает точки от navgraph.

### 4.5. `movement`

**Вход:** `movement_profile.json` (измеренные параметры) + weapon table.
**Выход:** `travel_time(route, state)`, `speed_profile`.
**Обязанности:**

- max speed по оружию;
- acceleration/friction/stop speed;
- crouch/walk/zoom modifiers;
- jump/drop/ladder;
- неопределённость параметров;
- калибровка по измерениям.

**Текущая реализация:** `movement/source.py` — straight-line ground;
`movement/route.py` — continuous/stop-go range, vertical/turn profile и
отдельный one-airtime `J+` jump budget. Turn/landing не откалиброваны.

**Граница:** не выбирает маршрут; оценивает время для заданного.

### 4.6. `simulation`

**Вход:** bundle + movement + scenario.
**Выход:** траектории/таймлайны агентов, метрики.
**Обязанности:**

- 5 T + 5 CT;
- spawn assignment (детерминированный/вероятностный);
- route choice;
- arrival times, meeting points, bottlenecks;
- блокировки/очереди (упрощённо);
- seed и воспроизводимость.

**Текущая реализация:** `simulation/scenario.py` — 5-man rush envelope и
split 2 A / 2 B / 1 Mid с optimal/random/softmax assignment; exact
`C(15,5)` наборов спавнов. Калибровка policy, blocking и combat ещё не
реализованы.

**Граница:** без боя/урона/экономики в MVP.

### 4.7. `balance`

**Вход:** результаты симуляции/маршрутов.
**Выход:** метрики + CIs + sensitivity.
**Обязанности:**

- time-to-point distributions;
- side difference;
- spawn spread;
- alternative route availability;
- bottleneck indicators;
- sensitivity to speed/route/spawn;
- запрет на единственный «balance score».

**Текущая реализация:** `simulation/balance.py` — time-only route verdict
(`balanced`/`CT advantage`/`T advantage`); не combat/win-rate.

### 4.8. `viz`

**Вход:** bundle + results.
**Выход:** SVG/PNG/HTML/3D.
**Обязанности:**

- nav polygons;
- representative + all spawn→target routes with animated reveal;
- heatmaps;
- debug overlays (one-way, anomalies);
- стабильные цвета/легенды.

### 4.9. `validation`

**Вход:** bundle + expected/golden.
**Выход:** отчёт pass/fail.
**Обязанности:**

- integrity, schema, counts, hashes;
- geometric invariants;
- cross-parser checks;
- regression snapshots;
- performance budgets.

### 4.10. `pipeline` (auto-generation)

**Вход:** пользовательские `.nav`, entity dump, physics glTF (позже — VPK/
установленная игра).
**Выход:** проверки, viewer, manifest с hashes/status.

**Текущая реализация:** `tools/auto_generate.py` — floor/wall/clearance
checks → viewer + summary + manifest; `app/server.py` — локальный
upload/drop + Generate API/job UI + map library. Viewer строит 90
spawn→target routes с animation.

**Граница:** detection/encounter times и combat ещё не реализованы; Release
0.2/0.3 в roadmap.

## 5. Формат Map Bundle

### 5.1. `manifest.json`

```json
{
  "schema_version": 1,
  "map": "de_dust2",
  "game": {
    "client_version": "2000933",
    "buildid": "25966348",
    "patch_version": "1.41.9.1"
  },
  "sources": {
    "map_vpk_sha256": "...",
    "nav_sha256": "...",
    "entities_sha256": "...",
    "collision_sha256": "..."
  },
  "tools": {
    "source2viewer": "20.1",
    "nav_schema": 1
  },
  "units": "hammer",
  "axes": "x-forward-y-left-z-up",
  "generated_at": "2026-10-19T00:00:00Z"
}
```

### 5.2. `nav.json`

```json
{
  "version": 36,
  "sub_version": 1,
  "is_analyzed": true,
  "generation": {
    "nav_gen_version": 13,
    "hulls": [
      {
        "radius": 16.0,
        "height": 71.0,
        "short_height": 35.5,
        "max_climb": 16.0,
        "max_slope": 50,
        "max_jump_up_dist": 68.0,
        "max_jump_down_dist": 157.0
      }
    ]
  },
  "areas": [
    {
      "id": 349,
      "hull": 0,
      "attribute_flags": 0,
      "corners": [[x, y, z], ...],
      "connections": [
        {"to": 348, "edge": 0, "kind": "walk"}
      ],
      "ladders_above": [],
      "ladders_below": []
    }
  ],
  "ladders": []
}
```

Derived fields (`kind`, `dz`, `one_way`, `boundary_dz`) можно хранить рядом,
но исходные поля не перезаписывать.

### 5.3. `entities.json`

```json
{
  "spawns": {
    "T": [{"origin": [x, y, z], "area_id": 369}],
    "CT": [{"origin": [x, y, z], "area_id": 1242}]
  },
  "bombsites": [
    {"designation": "0", "models": ["..."]}
  ],
  "buyzones": [
    {"team": 2, "model": "..."}
  ],
  "places": [
    {"name": "Middle", "origin": [x, y, z], "area_id": 397}
  ]
}
```

### 5.4. `collision.glb`

- glTF 2.0, треугольники, материал/группа.
- Отдельно `collision_meta.json`: source, material groups, filters,
  decimation, bbox, triangle count, hash.
- Для анализа допустим компактный формат (`npz`/Parquet) после
  предварительной обработки; glTF — для визуальной проверки.

### 5.5. `metrics/*.json`

- route matrix;
- spawn distributions;
- diagnostics;
- simulation seeds/results.

## 6. Координаты и единицы

- Hammer units, Z-up.
- Nav, entity origins и collision — одна система; проверено на 30/30
  спавнах Dust2 (XY inside nav).
- Spawn/callout z не равен полу; использовать `area_plane_z` или центроид.
- Radar — отдельная 2D-проекция; не использовать для расчётов, только для
  визуализации.
- Все exported glTF проверять на отсутствие неожиданного transform.

## 7. Производительность

| Задача | Оценка | Решение |
|---|---|---|
| Parse nav 0.5 МБ | миллисекунды | Python stdlib |
| Dijkstra 2–4 тыс. узлов | миллисекунды | `heapq` |
| Line-graph 6–10 тыс. состояний | десятки мс | Python |
| 180 spawn→target маршрутов | секунды | кэш/предрасчёт |
| Collision 21.8 МБ Dust2 | сотни МБ RAM при triangles | NumPy/BVH, фильтрация |
| Collision 61 МБ Inferno | больше | потоковая загрузка/decimation |
| glTF-экспорт карты | минуты/память | offline ingest, не runtime |

**[INFERENCE]** Для MVP не нужен C++/Rust. Узким местом будет collision
geometry и визуализация, а не nav.

## 8. Ошибки и отказоустойчивость

- Несовпадение `ClientVersion`/build → fail.
- Nav `area_count == 0` → fail.
- Dangling connection → fail (или explicit warning с порогом).
- Spawn не найден в nav → fail для этой карты.
- Collision export отсутствует → bundle incomplete; анализ маршрутов возможен,
  collision-проверки — нет.
- Source2Viewer CLI вернул non-zero → сохранить stderr, не продолжать молча.
- Любой парсер не должен «догадываться» о формате: лучше упасть.

## 9. Тестирование архитектуры

- Unit: parser, point-in-poly, edge midpoint, Dijkstra.
- Integration: VPK → nav → graph → route на golden Dust2.
- Contract: manifest schema, bundle loader.
- Property: route length ≥ straight-line; reverse route finite; no negative
  costs; area IDs stable.
- Performance: parse/nav/routing budgets.
- Cross-tool: наш parser vs Awpy/VRF на одном `.nav`.
- Regression: golden counts/routes после обновления игры.

## 10. Windows-ограничения

- Не использовать неквалифицированный `Test-Path`.
- В Python — `pathlib.Path.exists()`.
- В PowerShell — `[System.IO.File]::Exists` / `[System.IO.Directory]::Exists`.
- Длинные пути и пробелы — `pathlib`/`subprocess` со списком аргументов, без
  `shell=True`.
- Не писать в каталог игры; temp — `%LOCALAPPDATA%\Temp\opencode\...`.
- Source2Viewer CLI может создавать `exceptions.txt` в рабочем каталоге;
  запускать в temp и проверять.

## 11. Что откладывается

- Полная 3D-визуализация.
- Собственный физический движок.
- Combat/economy/utility simulation.
- ML/RL для поведения.
- Realtime-сервис.
- Поддержка всех карт до стабилизации Dust2.
- Автоматическое обновление game assets.
