# RESEARCH — источники, инструменты и подтверждённые возможности

**Дата проверки:** 2026-10-19
**Окружение:** Windows, Python 3.13.3, Git 2.55.0, 7-Zip 23.01, установленная
Counter-Strike 2.

## 0A. Internal Source 2 engine research (2026-11-23)

**FACT — upstream library.** ValveResourceFormat `20.1.7467` is MIT-licensed and
provides in-process readers for compiled Source 2 resources, binary KV3,
Zstandard/LZ4, PHYS aggregate data and EntityLump. ValvePak `5.0.2.177` and
ValveKeyValue `0.70.0.499` are part of the same project. The CS2MB component
links these libraries; it does not launch Source2Viewer-CLI.

**FACT — observed resource layout.** On CS2 build `2000948` (2026-11-19), the
extracted `world_physics.vmdl_c` has four blocks: PHYS, CTRL, RED2, DATA. The
PHYS block is binary KV3 version 5 compressed with Zstandard. The
`default_ents.vents_c` resource has RED2 and DATA blocks; its DATA block is
binary KV3 version 5 compressed with LZ4. The PHYS block contains one part and
6 mesh descriptors plus 10,143 convex hull descriptors on Dust2.

**FACT — geometry and entities.** The internal converter emitted 39 primitives,
1,306,947 exported vertices and 435,649 triangles for Dust2, exactly matching the
historical Source2Viewer 20.1 reference. Entity output matched the local
`resourceinfo.exe -all` dump semantically: 415 entities, 15 T / 15 CT spawns, 43
callouts and identical origins (0.01-unit text rounding on one Inferno spawn).

**TESTED — nine active-duty maps.** de_dust2, de_mirage, de_nuke, de_inferno,
de_ancient, de_train, de_vertigo, de_anubis and de_overpass were extracted and
converted. Collision triangle counts ranged from 133,133 to 2,733,610; floor
agreement with the same NAV ranged from 97.34% to 99.54%, median absolute dz
3.78–4.0 Hammer units. Sphere/capsule primitives appear on de_anubis (52
capsules) and de_overpass (13 spheres, 524 capsules); they are tessellated with
bounded ring counts. See [VALIDATION.md](VALIDATION.md) for the table.

**INFERENCE — architecture choice.** Reimplementing binary KV3 plus Zstandard,
LZ4, PHYS and EntityLump in Python would duplicate a tested upstream parser
without improving the analysis model. A small first-party executable that links
the library in-process is the lower-risk route and keeps the Python analysis
layer stdlib-only. The component is self-contained, pinned and shipped with MIT
notices.

**LIMITS.** The validation is tied to the recorded CS2 build and VRF version.
CI uses synthetic resources, not the game files. Curved primitives are
tessellated approximations, not exact analytic collision. A future Valve format
change can require an engine update; the tool must then be revalidated before
claims are carried forward.

## 0B. Security and release audit (2026-11-23)

**Scope:** Python app, parsers, SRI C# source, NuGet lockfile, build and package
scripts, GitHub Actions, website JavaScript/HTML, upload and HTTP handlers, path
and process execution, release assets and Git contents.

**FACT — endpoint controls are tested.** Direct HTTP tests cover Host rejection,
missing/cross-origin POSTs, invalid JSON, invalid map names, oversized uploads,
malformed multipart data, invalid extensions, missing glTF sidecars, viewer path
confinement, job-limit rejection and process-tree termination.

**FACT — process cleanup.** The server caps simultaneous jobs at two, rejects
excess requests with HTTP 429, prunes stale job records and upload directories,
and terminates the Windows process tree on timeout. The current test starts a
parent process that spawns a child and verifies both are gone.

**FACT — release integrity.** The complete package is built from the repository,
contains SRI and a portable Python 3.13 runtime, and ships SHA-256 checksums and
an SPDX SBOM. The executable is not code-signed; hashes detect corruption but are
not a signature.

**LIMITS.** Viewer HTML generation is not a browser sandbox. Remote binding is
disabled. The security scan is a hygiene check, not a proof of security. Current
findings are recorded in `SECURITY.md` and `SECURITY_BACKLOG.md`.

## 0C. Visual identity research (2026-11-23)

**FACT — canonical source.** The root `logo.png` from the owner's original
repository is the canonical CS2MB identity. It is preserved byte-for-byte; its
SHA-256 is `03f11c8167907d4b243c1e2ff64953ea33848257eae51e09dcbed4a2f4876e06`.

**DECISION.** The invented vector logo variants were removed. The application,
website, README, favicon and social preview use the original PNG. Technical SVG
diagrams contain no invented brand mark. Current application and site
screenshots were captured from the running `v1.0.0-pre.1` build after the SRI
rename and security changes.

**LIMIT.** Screenshots are presentation evidence, not proof of algorithmic
correctness. The original logo's raster detail is preserved rather than traced
into an approximate vector mark.

## 0. Правила доказательности

В документе используются метки:

- **[FACT]** — проверено на установленной игре, в исходном коде или в
  документации; указан источник.
- **[TESTED]** — проверено экспериментально в этом исследовании.
- **[INFERENCE]** — вывод из нескольких подтверждённых фактов.
- **[HYPOTHESIS]** — гипотеза, требующая отдельной проверки.
- **[COMMUNITY]** — значение/утверждение из стороннего проекта, не проверенное
  по Valve-первоисточнику.

Интернет-поиск и чтение страниц в этом окружении работали. Все ссылки ниже
открывались 2026-10-19, если не указано иное.

## 1. Source 2 Viewer и ValveResourceFormat (VRF)

### 1.1. Репозиторий и лицензия

- Репозиторий: <https://github.com/ValveResourceFormat/ValveResourceFormat>
- Лицензия: MIT. Файл `LICENSE`:
  <https://github.com/ValveResourceFormat/ValveResourceFormat/blob/master/LICENSE>
- Последний стабильный релиз на дату проверки: **20.1**, опубликован
  **2026-10-15**:
  <https://github.com/ValveResourceFormat/ValveResourceFormat/releases/tag/20.1>
- В релизе есть Windows x64 CLI `cli-windows-x64.zip` и GUI
  `Source2Viewer.exe`; CLI не требует установленного .NET runtime (self-contained
  сборка). Это подтверждается составом релиза и документацией.
- Проект состоит из GUI, CLI и библиотеки `ValveResourceFormat`; VPK-часть
  вынесена в отдельный репозиторий `ValvePak`.

**[FACT]** VRF — не «официальный инструмент Valve». Это open-source
reverse-engineering проект сообщества. Его результаты полезны, но не являются
гарантией точности исходных данных.

### 1.2. Что VRF умеет

По документации и исходникам:

- читает VPK v1/v2, включая `_dir.vpk` + numbered chunks и self-contained map
  VPK;
- извлекает файлы без декомпиляции;
- декомпилирует `.vmap_c`, `.vwrld_c`, `.vwnod_c`, `.vents_c`, `.vmdl_c`,
  `.vphys_c`, `.vtex_c`, `.vmat_c` и другие ресурсы;
- экспортирует карты и модели в glTF/GLB;
- декомпилирует карту в `.vmap` для Hammer;
- содержит парсер `.nav` (`ValveResourceFormat.NavMesh.NavMeshFile`);
- предоставляет C# API и NuGet-пакеты `ValveResourceFormat`,
  `ValveResourceFormat.Renderer`, `ValvePak`.

Основные ссылки:

- CLI и параметры:
  <https://github.com/ValveResourceFormat/ValveResourceFormat/blob/master/docs/guides/command-line.md>
- Поддержка форматов и потери при экспорте:
  <https://github.com/ValveResourceFormat/ValveResourceFormat/blob/master/docs/guides/format-support.md>
- Экспорт карт (официальная документация проекта):
  <https://s2v.app/ValveResourceFormat/guides/exporting-maps.html>
- Исходник VPK reader:
  <https://github.com/ValveResourceFormat/ValvePak/blob/master/ValvePak/ValvePak/Package.Read.cs>
- Исходник nav parser:
  <https://github.com/ValveResourceFormat/ValveResourceFormat/tree/master/ValveResourceFormat/NavMesh>

### 1.3. Экспорт карт: что получается и что теряется

**[FACT]** По документации VRF, экспорт карты в glTF включает:

- геометрию мира ( brushes и meshes);
- статические пропы;
- материалы и текстуры (отдельные файлы);
- базовую информацию о материалах;
- солнце.

**[FACT]** glTF-экспорт карты **не включает**:

- запечённое освещение;
- point/spot lights;
- игровую логику;
- навигационную сетку.

**[INFERENCE]** glTF-экспорт карты не документирован как полный collision
export. Он не гарантирует наличие всех collision-слоёв (player clips,
невидимые стены, physics-only детали). Для проверки проходимости нужно
использовать отдельный `world_physics.vmdl_c` и/или `.vmap`-декомпиляцию, а не
предполагать, что map glTF уже содержит полную collision.

**[FACT]** Декомпиляция `.vmap` в Hammer восстанавливает:

- сущности всех entity lump;
- мировую render-геометрию, сваривая треугольники обратно в редактируемые
  полигоны;
- статические пропы;
- физическую геометрию для коллизий, у которых нет соответствующего
  render-меша;
- слои, overlay и surface properties.

**[FACT]** Данные, уже уничтоженные компилятором карты и не восстанавливаемые:

- границы prefab-инстансов;
- исходные группы и selection sets;
- параметры проекции overlay (восстанавливается приближённо);
- per-face lightmap scale;
- уровни subdivision (остаётся финальный tessellated mesh);
- per-light «No Shadow» в CS2.

**[FACT]** Не реализовано/ограничено в VRF на дату проверки:

- external reference meshes: модели, вваренные в Hammer-геометрию, используют
  только встроенные meshes; отдельные `.vmesh_c` могут быть потеряны;
- clutter / процедурные detail props не декомпилируются;
- physics spheres и capsules не превращаются в Hammer-геометрию;
- 3D skybox не пакуется автоматически;
- glTF/GLB имеет ограничение 2 ГБ для GLB; для больших карт рекомендуется
  `.gltf` с отдельными файлами;
- экспорт большой карты может требовать много памяти и времени.

**[INFERENCE]** Для **визуализации** glTF достаточно. Для **коллизий** нужно
отдельно проверить `world_physics.vmdl_c` и/или `.vmap`; нельзя считать, что
glTF-экспорт карты по определению содержит полную collision-модель.

### 1.4. Программное использование

- C#: `ValveResourceFormat` и `ValvePak` можно подключить как NuGet-пакеты.
- CLI: можно вызывать из Python через `subprocess`; это рекомендуемый вариант
  для импорта в MVP.
- CLI не гарантирует стабильность аргументов между версиями (явно указано в
  документации). Нужно pin-ить версию и писать wrapper-тесты.
- Для запуска CLI на папке игры полезен `--game <gameinfo.gi или папка>`,
  иначе ссылки на материалы/модели могут не разрешаться.
- `--vpk_list`/`--vpk_dir` — список файлов и метаданные.
- `--vpk_filepath` — фильтр по пути.
- `--vpk_extensions vents_c -o -` — вывод entity lump в stdout.
- `--gltf_export_format gltf` — экспорт mesh/model/map в glTF.

### 1.5. Ограничения лицензии и данных

- Код VRF/ValvePak — MIT; можно использовать в приложении при сохранении
  copyright notice.
- Извлечённые игровые ресурсы — собственность Valve; лицензия MIT на код не
  распространяется на ассеты.
- Нельзя публиковать большие извлечённые ресурсы без отдельного согласования.

### 1.6. Практическая проверка VRF на collision

**[TESTED]** Source2Viewer-CLI 20.1 Windows x64 был скачан в temp, SHA-256
`67AAF8A67A85CA60FD09FF343E62103A4CDF3A2D177FC656231D7D734C5B3AA3`
совпал с digest релизного asset. CLI:

```text
Source2Viewer-CLI.exe -i world_physics.vmdl_c \
  -o world_physics.gltf -d --gltf_export_format gltf \
  --gltf_export_materials --game game/csgo/gameinfo.gi
```

Результат для Dust2:

- `world_physics_physics.gltf` 57 337 байт;
- `world_physics_physics.bin` 47 050 092 байта;
- 39 материалов/primitives;
- 1 306 947 vertices, 435 649 triangles;
- материалы `physics_group_*`, `physics_passbullets_*`,
  `physics_npcclip_playerclip_*`, `physics_csgo_grenadeclip`, `physics_sky`;
- node matrix масштабирует в meters/Y-up, но **локальные POSITION accessor'ы
  остаются в Hammer units/Source axes**. Для анализа node matrix нужно
  игнорировать; это проверено на T/CT/Mid/A/B.

**[FACT]** Source2Viewer CLI при указании `--game` ожидает путь к
`gameinfo.gi`, а не к папке (в отличие от `resourceinfo.exe`, которому нужна
папка). Это важно для wrapper-а.

**[TESTED]** Floor test на 8812 samples дал 98.77% совпадений в пределах 16
Hammer units; подробности — `docs/MAP_DATA.md`, раздел 10.2.

## 2. Awpy и навигационные сетки CS2

### 2.1. Репозиторий, версия, лицензия

- Репозиторий: <https://github.com/pnxenopoulos/awpy>
- Лицензия: MIT.
- Последний релиз на дату проверки: **Awpy Python 3.1.0**, опубликован
  **2026-10-17**:
  <https://github.com/pnxenopoulos/awpy/releases/tag/awpy-python-v3.1.0>
- Документация nav: <https://awpy.readthedocs.io/en/latest/modules/nav.html>
- Исходник nav parser:
  <https://github.com/pnxenopoulos/awpy/blob/main/crates/awpy/src/nav.rs>
- `awpy-data` (ассеты nav/radar/geometry):
  <https://github.com/pnxenopoulos/awpy-data>

### 2.2. Что поддерживает Awpy

**[FACT]** Текущий `nav.rs` Awpy:

- поддерживает Source 2 `.nav` версий **30–36**;
- явно указывает, что CS2 сейчас поставляет версию **36**;
- читает:
  - `area_id`;
  - `hull_index`;
  - `dynamic_attribute_flags` (на самом деле это file attribute flags; см.
    ниже);
  - corners;
  - connections (только `area_id`, `edge_id` отбрасывается);
  - `ladders_above` / `ladders_below` как ID;
  - `is_analyzed`, `version`, `sub_version`;
- умеет `find_area(point)` и `find_path(start, end)` с весами `distance`,
  `hops`, `size`;
- `find_area` учитывает перекрывающиеся этажи, выбирая область с ближайшей
  высотой центроида;
- `find_path` — Dijkstra по графу областей;
- `NavMesh` может загрузить локальный `.nav` или скачать ассет из `awpy-data`
  по имени карты и версии.

**[FACT]** `awpy-data` README описывает pipeline:

- `navs.zip` — `<map>.nav`;
- `geometry.zip` — `<map>.mesh` (AWMH), полученный из
  `world_physics.vmdl_c`;
- `images.zip` — radars;
- `map_data.json` — transform world → radar;
- релизы привязаны к CS2 `ClientVersion`;
- для извлечения используется `Source2Viewer-CLI`;
- collision geometry фильтруется: удаляются non-occluders (player/grenade
  clips, sky, glass, windows, bullet-pass railings), затем вершины свариваются
  и меш decimate-ится.

**[INFERENCE]** Awpy удобен как:
- независимый парсер для cross-check нашего loader;
- источник готовых nav/geometry артефактов;
- baseline для `find_area`/`find_path`.

**[INFERENCE]** Awpy **не заменяет** наш слой по нескольким причинам:
- не парсит глобальную таблицу ladders (только ID в областях);
- не парсит places, generation params, transformed bounds и CS2 custom data;
- не отдаёт `edge_id` наружу, поэтому нельзя точно восстановить точки
  пересечения рёбер;
- не содержит collision/visibility модели в nav-модуле;
- `awpy-data` — это внешние ассеты, привязанные к версии; для локальной
  установки надёжнее читать `.nav` из map VPK.

### 2.3. Терминологическая неточность

**[FACT]** VRF `NavMeshArea.cs` явно указывает: в файле хранятся **base
attribute flags** (`NavAttributeFlags`), а runtime dynamic attribute flags
(32-битные) в файле не сохраняются.

Awpy называет это поле `dynamic_attribute_flags`. Это удобно для API, но
вводит в заблуждение. В нашей модели поле называется `attribute_flags`, а
runtime-атрибуты, если понадобятся, должны быть отдельными.

### 2.4. Источники `.nav`

- Штатный источник: `game/csgo/maps/<map>.vpk` → `maps/<map>.nav`.
- `awpy-data` releases — копии nav, привязанные к ClientVersion.
- `csgo/maps/graphs/*.ain` в установленной игре — не nav; файлы по 16 байт,
  похожи на legacy-заглушки. Не использовать.
- Vanity VPK (`<map>_vanity.vpk`) — усечённые сцены для меню, nav там нет.
- Workshop preview VPK (`workshop_preview_*.vpk`) — nav может быть 247 байт с
  нулём областей; не использовать как игровую карту.

## 3. Формат `.nav` Source 2: подтверждённая структура

### 3.1. Источники

- VRF:
  - `NavMeshFile.cs` — заголовок, places, movable meshes, areas, ladders,
    transformed bounds, generation params, custom data;
  - `NavMeshArea.cs` — area record, connections, hiding spots, ladders;
  - `NavMeshLadder.cs` — глобальная таблица лестниц;
  - `NavMeshGenerationParams.cs` / `NavMeshGenerationHullParams.cs` — параметры
    генерации;
  - `NavAttributeFlags.cs` — флаги областей.
- Awpy `nav.rs` — упрощённый парсер v30–36.
- Наш `tools/nav_inspect.py` — независимая реализация для исследования,
  проверенная на всех nav установленных карт.

### 3.2. Порядок блоков (v36, CS2)

**[FACT]** Подтверждено по VRF и нашему parser:

```text
magic = 0xFEEDFACE
version = u32
sub_version = u32
is_analyzed = u8
place_count = u16
  place_name: u16 length + bytes
has_unnamed_areas = u8
if version >= 36: KV3 MovableMeshSettings
if version >= 31:
  corner_count = u32; corners: vec3[]
  polygon_count = u32
  polygon: u8 corner_count; u32 corner_indices[]; if v>=35 u32 movable_mesh_id
if version >= 32:
  corner_gravity_flags = u32
  optional gravity_count + vec3[]
if version >= 35:
  movable_mesh_count = u32
  movable_mesh: cstring + 48-byte matrix
if version >= 36: KV3 GameData
area_count = u32
  area:
    area_id u32
    attribute_flags i64
    hull_index u8
    polygon_index u32
    unused f32
    for each corner/edge: connection_count u32
      connection: area_id u32, edge_id u32
    hiding_spot_count u8; hiding spots: id u32, pos vec3, flags u8
    encounter_path_count u32 (в CS2 0)
    ladders_above: count u32 + u32[]
    ladders_below: count u32 + u32[]
ladder_count u32
  ladder: id, width, top vec3, bottom vec3, length, direction,
          top_forward/top_left/top_right/top_behind/bottom_area,
          bottom_left/bottom_right (v>=33)
transformed_bounds_count i32 + 72 bytes per record
generation_params:
  nav_gen_version i32
  ...
  hull params (radius, height, short height, crawl, max climb, max slope,
  max jump down, max jump horiz base, max jump up, border erosion)
if version >= 36: KV3 ExtraGenerationParams
if sub_version > 0: KV3 CustomData
```

**[TESTED]** Наш parser прочитал **все 28 nav-файлов** из map VPK
установленной игры (включая preview/legacy-карты); для каждого
`bytes_consumed == file size`. Это сильная проверка того, что layout и пропуск
KV3-документов корректны.

### 3.3. Семантика `edge_id`

**[TESTED]** Мы проверили гипотезу на 6100 взаимных парах связей `de_dust2`:

| Гипотеза | Медиана расстояния между серединами рёбер | < 20 units |
|---|---:|---:|
| `edge_id` — ребро **source** | 51.9 | 1730 / 6100 |
| `edge_id` — ребро **destination** | 0.0 | 4854 / 6100 |

Вывод: `edge_id` в связи `A -> B` относится к ребру **B**, через которое
маршрут входит в B. Это важно для точной длины: нельзя использовать середину
ребра A.

**[INFERENCE]** Для one-way связи без обратного ребра точная точка входа всё
равно приблизительна; нужна проверка по collision geometry.

### 3.4. Что есть в nav, а чего нет

| Есть | Нет / ограничено |
|---|---|
| `area_id`, выпуклые полигоны, высоты | Точная collision geometry |
| Направленные связи, one-way | `edge_id` в Awpy наружу не отдаётся |
| `attribute_flags` (Jump, CrouchHeight, Stairs, ...) | Runtime dynamic attributes |
| Ladders: ID, top/bottom, direction, area refs | Геометрия лестниц как collision |
| Places (может быть пустым) | Семантика спавнов/bombsite |
| Movable mesh IDs и transforms (v35+) | Динамические двери/пропы в реальном времени |
| Hiding spots / CS2 custom bot data | Полная боевая/тактическая модель |
| Generation params (hull, max climb/jump) | Скорости, ускорение, friction игрока |
| `is_analyzed`, версия | Точная видимость (нужны collision triangles) |

### 3.5. Практический вывод

**[INFERENCE]** Nav достаточно для:
- глобального графа маршрутов;
- оценки длины и числа областей;
- поиска компонент, one-way, узких мест;
- распределения времени прибытия после добавления модели движения.

**[INFERENCE]** Nav недостаточно для:
- проверки, что между областями нет стены/пропа;
- ширины прохода и высоты;
- line-of-sight;
- точного прыжка/дропа/boost;
- динамических дверей и breakables;
- тактической симуляции.

## 4. `cs2-nav` (Rust/Python)

- Репозиторий: <https://github.com/JanEricNitschke/cs2_meeting_points>
- Пакет: `cs2_nav`, версия в `Cargo.toml` на дату проверки: **0.3.20**
- Лицензия: MIT.
- Компоненты:
  - `Nav`/`NavArea` — парсер и граф (ядро взято из Awpy `nav.rs`);
  - `PathResult` — маршруты;
  - `CollisionChecker` / `VisibilityChecker` — BVH по треугольникам из `.tri`;
  - `Position`, `Triangle`, утилиты.
- `.tri` — простой массив треугольников (9 f32 на треугольник), не является
  частью игры; его нужно получить из collision geometry.
- Полезен для:
  - независимой проверки nav;
  - быстрого Rust-бэкенда;
  - видимости/raycast, если есть `.tri`.
- Ограничения:
  - collision checker требует подготовленный `.tri`, а не читает
    `world_physics.vmdl_c` напрямую;
  - не является полноценной физикой движения;
  - часть констант движения — community-значения (см. ниже).

## 5. `resourceinfo.exe` (Valve, установленная игра)

- Путь: `game/bin/win64/resourceinfo.exe`.
- Официальный диагностический инструмент Valve, найден в установке.
- Умеет: `-all`, `-b <block>`, `-raw`, `-strings`, `-dep`, `-game <dir>`.
- **[TESTED]** Мы использовали его для дампа `default_ents.vents_c`,
  `weapons.vdata_c` и `world_physics.vmdl_c`; файлы игры не изменялись.
- **[TESTED]** `resourceinfo -b PHYS` выводит `VPhysXAggregateData_t` как
  KV3-текст. Для Dust2 dump — 166 МБ / ~2 млн строк; в нём видны
  `m_parts`, `m_hulls`, `m_Vertices`, `m_VertexPositions`, `m_Edges`,
  `m_Faces`, `m_Planes`, `m_collisionAttributes`. Это позволяет извлекать
  hull bounds и collision attributes без Source2Viewer, но default dump может
  усекать большие hex-блобы; для полных треугольников нужен VRF или
  бинарный parser `RnHull_t`.
- **[FACT]** Публичной документации на уровне VRF нет; поведение может
  меняться. Для production нельзя делать его единственной зависимостью.
- **[INFERENCE]** Отличный fallback для проверки сущностей, оружия и
  collision-атрибутов, когда VRF CLI ещё не установлен.

## 6. Другие инструменты и что с ними не так

| Инструмент | Статус | Пригодность |
|---|---|---|
| 7-Zip 23.01 | установлен | **[TESTED]** не открывает Source 2 VPK: `Cannot open the file as archive`. Не использовать. |
| ValvePak (C#) | open source, MIT | Основной кандидат для production VPK I/O. |
| VRF CLI | release 20.1, MIT | Основной кандидат для извлечения/декомпиляции/glTF. |
| VRF library | C#, MIT | Если нужен in-process импорт без CLI. |
| Awpy | 3.1.0, MIT | Baseline/cross-check nav и demo parsing. |
| cs2-nav | 0.3.20, MIT | Rust/Python nav/visibility, требует `.tri`. |
| `resourceinfo.exe` | в игре | Диагностика, не API. |
| `dmxconvert.exe` | в игре | DMX-конвертация; для нашей задачи не нужен. |
| `vpk.exe` | в CS2 отсутствует | Нельзя использовать как Valve-упаковщик. |
| `demoparser` / `demoinfocs-golang` / `clarity` | сторонние demo parsers | Полезны для валидации маршрутов по реальным демкам, не для геометрии карты. |

## 7. Данные о движении

### 7.1. Что удалось подтвердить из установленной игры

**[FACT]** `scripts/weapons.vdata_c` (в `pak01_dir.vpk`) содержит
`m_flMaxSpeed` для классов оружия. Значения из установленной сборки:

| Класс | `m_flMaxSpeed` |
|---|---|
| `weapon_knife` | 250 |
| `weapon_c4` | 250 |
| `weapon_ak47` | 215 |
| `weapon_m4a1` | 225 |
| `weapon_awp` | 200 / 100 |
| `weapon_ssg08` | 230 |
| `weapon_glock` | 240 |
| `weapon_deagle` | 230 (также встречается 180/220) |
| `weapon_hegrenade` | 245 |
| `weapon_flashbang` | 245 |
| `weapon_smokegrenade` | 245 |
| `weapon_molotov` | 245 |
| `weapon_incgrenade` | 245 |

Полный список 41 класса можно получить из дампа `resourceinfo`; в таблице
выше — ключевые. Два значения для AWP/AUG/SG553/G3SG1/SCAR20, вероятно,
относятся к обычному/zoom-режиму, но это **[HYPOTHESIS]** и требует проверки.
Для Deagle в дампе есть несколько определений; нужно выбрать активное.

**[FACT]** `cfg/gamemode_competitive.cfg` установленной игры содержит:

- `mp_freezetime 15`
- `mp_roundtime_defuse 1.92` (минуты; ≈115.2 с)
- `mp_randomspawn 0`
- `sv_allow_approximate_spawns 0`
- `mp_buy_anywhere 0`
- `mp_solid_teammates 1`

Это важно: стартовые точки, вероятно, назначаются не случайно, а по слотам;
наш разброс «min/median/max по 15 спавнам» — это **огибающая**, а не
распределение вероятностей.

**[FACT]** `cfg/moddefaults.txt` — это dxsupport, а не movement convars;
`sv_accelerate`, `sv_friction`, `sv_maxspeed` там не найдены. Значения ниже
прочитаны из running game через консоль.

**[TESTED]** Локальный CS2 listen server, `de_dust2`, 2026-10-19:

| Convar | Значение |
|---|---:|
| `sv_accelerate` | 5.5 |
| `sv_friction` | 5.2 |
| `sv_stopspeed` | 80 |
| `sv_maxspeed` | 320 |
| `sv_airaccelerate` | 12 |
| `sv_air_max_wishspeed` | 30 |
| `sv_gravity` | 800 |
| `sv_jump_impulse` | 301.993 |
| `sv_ladder_scale_speed` | 0.78 |
| `sv_staminamax` | 80 |

**[TESTED]** Установившиеся скорости по `cl_showpos` в верхнем туннеле:

| Состояние | Измерено |
|---|---:|
| AK-47 | 215.00 |
| Knife | 250.00 |
| AWP | 200.00 |
| AK walk (`Shift`) | 111.80 |
| AK crouch (`Ctrl`) | 73.10 |

**[INFERENCE]** Walk/crouch — модификаторы 0.52/0.34 от скорости оружия:
`215 * 0.52 = 111.8`, `215 * 0.34 = 73.1`. Присед не фиксированные 85;
85 — это knife 250 * 0.34.

**[FACT]** Формулы acceleration/friction реализованы по Source SDK
`CGameMovement::Accelerate` / `Friction`:
<https://github.com/ValveSoftware/source-sdk-2013/blob/master/src/game/shared/gamemovement.cpp>.
CS2 не доказан как идентичный Source 1; модель откалибрована по измеренным
steady-state, но crouch ниже `sv_stopspeed` потребовал effective
`friction_floor = min(stopspeed, target_speed)`.

Подробности и ограничения: [MOVEMENT.md](MOVEMENT.md).

### 7.2. Community-значения и расхождения

`cs2-nav/src/constants.rs` содержит:

- `RUNNING_SPEED = 250` — подтверждается для knife;
- `CROUCHING_SPEED = 85` — верно только для knife (250*0.34), не для AK;
- `GRAVITY = 800` — подтверждено;
- `JUMP_HEIGHT = 55.83` — расходится с `301.993^2/(2*800)=57.0`;
- `PLAYER_HEIGHT = 72`, `PLAYER_WIDTH = 32` — не проверялось в этой сессии;
- ladder speed `250 * 2 * 0.78` — гипотеза, не измерялась;
- `DEFAULT_SERVER_TICKRATE = 128` — не проверялся;
- `DEFAULT_FREEZE_TIME_IN_SECS = 20` — competitive cfg показывает 15.

**[INFERENCE]** Community-константы полезны как ориентир, но не заменяют
измерение. Особенно это касается crouch (weapon-dependent) и freeze time.

## 8. Итоговая оценка инструментов

**[INFERENCE]** Минимальный работающий стек:

1. **Source2Viewer-CLI** — извлечение VPK, entity dump, `world_physics.vmdl_c`
   → glTF, map glTF при необходимости.
2. **Собственный Python loader** — `.nav` и промежуточная модель; без runtime
   зависимости от игры.
3. **Awpy / cs2-nav** — независимая проверка nav и, при наличии `.tri`,
   видимости.
4. **`resourceinfo.exe`** — вспомогательная проверка сущностей/оружия.
5. **Python + stdlib** — анализ, графы, тесты. NumPy/SciPy/Shapely добавлять
   только после подтверждения необходимости.

**[INFERENCE]** Писать собственный парсер Source 2 ресурсов целиком не нужно:
VRF уже покрывает VPK, `.vmap`, `.vmdl`, `.vents`, PHYS и glTF. Собственный
код оправдан только для узкого `.nav`-loader и промежуточной модели.

## 9. Ссылки: сводная таблица

| Тема | Первичный источник | Дата/версия |
|---|---|---|
| VRF релиз | <https://github.com/ValveResourceFormat/ValveResourceFormat/releases/tag/20.1> | 2026-10-15, 20.1 |
| VRF лицензия | <https://github.com/ValveResourceFormat/ValveResourceFormat/blob/master/LICENSE> | MIT |
| VRF CLI | <https://github.com/ValveResourceFormat/ValveResourceFormat/blob/master/docs/guides/command-line.md> | master, 2026-10-19 |
| VRF format support | <https://github.com/ValveResourceFormat/ValveResourceFormat/blob/master/docs/guides/format-support.md> | master, 2026-10-19 |
| VRF map export | <https://s2v.app/ValveResourceFormat/guides/exporting-maps.html> | 2026-10-19 |
| ValvePak reader | <https://github.com/ValveResourceFormat/ValvePak/blob/master/ValvePak/ValvePak/Package.Read.cs> | master |
| VRF nav parser | <https://github.com/ValveResourceFormat/ValveResourceFormat/tree/master/ValveResourceFormat/NavMesh> | master |
| Awpy релиз | <https://github.com/pnxenopoulos/awpy/releases/tag/awpy-python-v3.1.0> | 2026-10-17, 3.1.0 |
| Awpy nav docs | <https://awpy.readthedocs.io/en/latest/modules/nav.html> | 2026-10-19 |
| Awpy nav source | <https://github.com/pnxenopoulos/awpy/blob/main/crates/awpy/src/nav.rs> | main, 2026-10-19 |
| awpy-data | <https://github.com/pnxenopoulos/awpy-data> | main, 2026-10-19 |
| cs2-nav | <https://github.com/JanEricNitschke/cs2_meeting_points> | 0.3.20, 2026-10-19 |
| cs2-nav constants | <https://github.com/JanEricNitschke/cs2_meeting_points/blob/main/src/constants.rs> | community |
| Source 2 VPK format | <https://www.source2.wiki/FileFormats/vpk> | secondary, 2026-10-19 |
| Valve nav format (legacy) | <https://developer.valvesoftware.com/wiki/NAV_(file_format)> | 2026-06-26 |
| CS2 movement (legacy reference) | <https://developer.valvesoftware.com/wiki/Counter-Strike:_Global_Offensive/Mapper%27s_Reference> | community/reference |
| Source SDK movement code | <https://github.com/ValveSoftware/source-sdk-2013/blob/master/src/game/shared/gamemovement.cpp> | Source 1 reference |
