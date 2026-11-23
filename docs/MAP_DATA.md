# MAP_DATA — фактическая структура ресурсов CS2 и результаты эксперимента

**Дата:** 2026-10-19
**Игра:** `<CS2_GAME>`
**Проект:** `<PROJECT_ROOT>`

## 1. Версия установленной игры

Из `appmanifest_730.acf` и `game/csgo/steam.inf`:

| Параметр | Значение |
|---|---|
| appid | 730 |
| ProductName | cs2 |
| ClientVersion | 2000933 |
| ServerVersion | 2000933 |
| PatchVersion | 1.41.9.1 |
| SourceRevision | 11133601 |
| VersionDate | Oct 15 2026 |
| VersionTime | 10:15:52 |
| Steam buildid | 25966348 |
| LastUpdated (UTC) | 2026-10-17 06:51:43 |

Это версия, к которой относятся все числа ниже. При обновлении CS2 nav,
entities и collision нужно пересобрать и сравнить хэши.

> **Provenance update (2026-11-21):** установленный `appmanifest` в ходе
> maintenance-проверки сообщал buildid `26798866`. Для `de_dust2.nav` SHA-256
> совпал с записанным ниже (`64BBC202…64E1EA7`), поэтому данные nav этой карты
> на момент проверки не изменились. Остальные карты и collision/entity ресурсы
> не перепроверялись; не считайте это общей ревалидацией.

## 2. Структура каталогов

```text
Counter-Strike Global Offensive/
├─ game/
│  ├─ bin/win64/                 # cs2.exe, resourceinfo.exe, navsystem.dll, ...
│  ├─ core/                      # core pak01, FGD, tools
│  └─ csgo/
│     ├─ pak01_dir.vpk           # индекс основного контента
│     ├─ pak01_000.vpk ... 504   # chunks
│     ├─ maps/
│     │  ├─ de_dust2.vpk         # self-contained map VPK
│     │  ├─ de_dust2_vanity.vpk  # усечённая сцена для меню
│     │  └─ ...
│     └─ cfg/
│        ├─ gamemode_competitive.cfg
│        └─ ...
└─ csgo/
   └─ maps/
      ├─ graphs/*.ain            # 16-byte legacy-заглушки
      └─ workshop/               # загруженные workshop-карты
```

**[FACT]** `game/csgo/maps/*.vpk` — отдельный self-contained VPK на карту.
Официальные игровые карты содержат `maps/<map>.nav` и `maps/<map>/...`
ресурсы. Vanity-версии не содержат nav и не должны использоваться для анализа.

## 3. Структура map VPK на примере `de_dust2.vpk`

**[TESTED]** Заголовок VPK:

- magic `0x55AA1234`;
- version 2;
- tree size `36 011` байт;
- file data section `262 432 236` байт;
- 632 записи;
- размер файла `262 476 433` байт;
- SHA-256 `51D6BB432B6553BFAE6C38219A527C5DE2464A2B107080F2B8BE7D8427EBB885`.

Распределение расширений:

| Расширение | Кол-во | Что это |
|---|---:|---|
| `vmdl_c` | 570 | мировые агрегаты, статические пропы, entity-модели |
| `dat` | 43 | данные light probe / octree |
| `vtex_c` | 7 | текстуры (cubemap, lightmaps) |
| `vrman_c` | 3 | resource manifests |
| `occlusion` | 1 | occlusion-данные |
| `nav` | 1 | `maps/de_dust2.nav` |
| `vmap_c` | 1 | `maps/de_dust2.vmap_c` |
| `vdata_c` | 1 | map vdata |
| `vents_c` | 1 | `maps/de_dust2/entities/default_ents.vents_c` |
| `kv3` | 1 | `lightmap_query_data.kv3` |
| `vwrld_c` | 1 | `maps/de_dust2/world.vwrld_c` |
| `vvis_c` | 1 | `maps/de_dust2/world_visibility.vvis_c` |
| `vwnod_c` | 1 | `maps/de_dust2/worldnodes/n0.vwnod_c` |

**[FACT]** Отдельного `maps/de_dust2.vphys_c` в map VPK нет. Из всех map VPK
в `game/csgo/maps` (44 файла, включая vanity/preview) standalone `.vphys_c`
встретился только в `cs_italy.vpk` (2 записи) и `lobby_mapveto.vpk` (1).
Основная collision-геометрия лежит в `maps/<map>/world_physics.vmdl_c`.

## 4. Ресурсы и способы чтения

| Тип данных | Фактический источник | Подтверждённый способ чтения | Промежуточный формат | Ограничения |
|---|---|---|---|---|
| Nav mesh | `maps/<map>.vpk` → `maps/<map>.nav` | наш `tools/nav_inspect.py`; VRF `NavMeshFile`; Awpy `NavMesh` | JSON / Parquet | Абстракция для ботов, не collision |
| Entity lump | `maps/<map>/entities/default_ents.vents_c` | `resourceinfo.exe -game <dir> -i ... -all`; VRF `EntityLump` | JSON / text | В некоторых картах несколько `vents_c` (до 6) |
| World collision | `maps/<map>/world_physics.vmdl_c` | VRF/CLI → glTF; PHYS block | glTF + metadata | 21.8 МБ Dust2, 61.3 МБ Inferno; требует фильтрации |
| World render | `.vmap_c`, `world.vwrld_c`, `worldnodes/n0.vwnod_c`, 570 `vmdl_c` | VRF map export → glTF/vmap | glTF | Не содержит полную collision; тяжёлый экспорт |
| Static props | `worldnodes/*.vmdl_c`, entity models | VRF → glTF/vmap | glTF | Часть collision может быть в `world_physics` |
| Callouts / spawns / bomb sites | `default_ents.vents_c` | `resourceinfo` / VRF EntityLump | JSON | Origins могут быть выше пола |
| Buyzones | `default_ents.vents_c` (`func_buyzone`) | то же | JSON | Brush model, origin часто 0 |
| Weapon speeds | `pak01_dir.vpk` → `scripts/weapons.vdata_c` | `resourceinfo -all` | JSON/table | Не все глобальные параметры движения |
| Game rules | `game/csgo/cfg/gamemode_competitive.cfg` | прямое чтение | config | Не содержит `sv_accelerate`/friction |
| Radar / overview | `pak01_dir.vpk` | VRF → PNG; overview KV | PNG + JSON | Нужен transform; не критично для маршрутов |
| Visibility | `.vvis_c`, collision geometry | VRF / collision triangles | BVH | Требует collision export |
| Ladders | `.nav` | наш parser / VRF | JSON | В Dust2 0; в других картах есть |

## 5. Nav census: все официальные карты

**[TESTED]** `tools/nav_census.py` прочитал все nav-файлы из
`game/csgo/maps/*.vpk` в память (без извлечения на диск) и проверил
`bytes_consumed == file size` для каждого файла. Ошибок разбора нет.

Выборка (полная таблица — `artifacts/nav_census.tsv`, не коммитится):

| Map VPK | Nav ver | Areas | Edges | Ladders | Undirected comp. | SCC | Largest SCC | One-way | Vertical anomalies* |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| de_dust2 | 36 | 2242 | 6275 | 0 | 1 | 12 | 2186 | 175 | 2 (+1 non-reciprocal) |
| de_mirage | 36 | 2544 | 6381 | 2 | 2 | 23 | 2407 | 307 | 0 |
| de_inferno | 36 | 2738 | 7068 | 0 | 1 | 9 | 2707 | 144 | 1 |
| de_nuke | 36 | 3040 | 7676 | 6 | 2 | 24 | 2531 | 332 | 5 |
| de_ancient | 36 | 1969 | 5085 | 0 | 1 | 5 | 1937 | 77 | 0 |
| de_anubis | 36 | 2633 | 6877 | 0 | 1 | 4 | 2613 | 129 | 1 |
| de_overpass | 36 | 3938 | 10016 | 1 | 2 | 10 | 3891 | 148 | 5 |
| de_vertigo | 36 | 2105 | 5321 | 1 | 3 | 14 | 2051 | 177 | 3 |
| de_train | 36 | 2154 | 5454 | 11 | 2 | 16 | 2021 | 222 | 0 |
| de_cache | 36 | 2209 | 5748 | 1 | 2 | 25 | 2058 | 232 | 2 |

\* Vertical anomalies считаются только для reciprocal-связей по разнице высот
на границе и лимитам generation params. Для Dust2 отдельно найдена
non-reciprocal связь `834 -> 748` с ΔZ = −181.

Наблюдения:

- Все конкурентные карты используют nav **v36**; встречаются v35
  (`ar_pool_day`, `cs_italy`, `lobby_mapveto`, preview-карты).
- Nav не всегда один компонент: `de_train`, `de_nuke`, `de_overpass`,
  `de_vertigo`, `de_cache` имеют 2–3 undirected components. Нельзя предполагать,
  что все области достижимы.
- Ladders есть не на всех картах; Dust2 — 0, Train — 11, Nuke — 6.
- SCC меньше общего числа областей почти везде; one-way связи — норма, а не
  ошибка.
- Generation params зависят от карты/версии. Например, v35-карты
  `ar_pool_day` и `cs_italy` имеют radius 15, height 71, max climb 17.5,
  max jump up 0, max jump down 240; `lobby_mapveto` (v35) — 16/71/16/68/157.
  Поэтому `vertical_anomalies` нельзя сравнивать между картами без учёта
  generation params.
- Preview-nav (`workshop_preview_*.vpk`) содержит 247 байт и 0 областей;
  такие файлы нужно отвергать по `area_count > 0`.

## 6. `de_dust2.nav`: детальная проверка

**[TESTED]** Файл:

```text
maps/de_dust2.nav
size = 481 872 bytes
SHA-256 = 64BBC202EDAE8A92D432368E86948BBEE3AF9C56555E190DDA251D28C64E1EA7
magic = 0xFEEDFACE
version = 36
sub_version = 1
is_analyzed = true
```

Содержимое:

| Свойство | Значение |
|---|---|
| Areas | 2242 |
| Area ID range | 1..2242, без пропусков и дублей |
| Polygon vertices | 1329 треугольников, 913 четырёхугольников |
| Edges | 6275 |
| Reciprocal edges | 97.21% |
| One-way edges | 175 |
| Degree min/mean/max | 1 / 2.799 / 15 |
| Undirected components | 1 |
| SCC | 12; размеры `[2186, 24, 11, 7, 5, 3, 1, 1, 1, 1, 1, 1]` |
| Ladders | 0 |
| `attribute_flags` | 2228 × 0; 14 × 65536 (`CrouchHeight`) |
| Zero-area polygons | 1 |
| Z range | −174 .. 194 |
| Places | пусто (`place_count=0`) |
| `has_unnamed_areas` | true |
| Generation params | nav_gen_version 13, radius 16, height 71, short height 35.5, max climb 16, max slope 50°, jump up 68, jump down 157, border erosion 0 |
| KV3 docs | `MovableMeshSettings` (9 bytes body), `GameData` (9 bytes body), `ExtraGenerationParams`, `CustomData` |
| Bytes consumed | 481 872 == file size |

**[FACT]** Все 2242 области имеют `hull_index = 0`; отдельного crouch-hull в
файле нет, но 14 областей помечены `CrouchHeight`.

### 6.1. Вертикальные аномалии

По generation limits:

| From → To | Boundary ΔZ | Тип | Комментарий |
|---|---:|---|---|
| 215 → 244 | +87 | reciprocal | выше `max_jump_up_dist=68`; требует ручной проверки |
| 1032 → 1015 | +88 | reciprocal | выше `max_jump_up_dist=68` |
| 834 → 748 | −181 | non-reciprocal | ниже `-max_jump_down_dist=-157` |

Это не обязательно ошибки Valve: возможны специальные переходы, boost,
или особенности генерации. Но автоматическая проверка должна их помечать.
**[INFERENCE]** Это ровно тот класс дефектов, который нужно сопоставлять с
collision geometry и ручным осмотром.

## 7. Entity lump: спавны, bombsite, callouts

**[TESTED]** `maps/de_dust2/entities/default_ents.vents_c`:

- size 45 073;
- блоки `RED2` (1409) + `DATA` (43 601);
- `resourceinfo.exe -all` дал 403 450 байт текста;
- 415 сущностей с `origin`;
- **15** `info_player_terrorist`;
- **15** `info_player_counterterrorist`;
- **43** `env_cs_place` с callout-именами;
- 2 `func_bomb_target` с `bomb_site_designation` 0/1;
- 2 `func_buyzone` с `TeamNum` 2/3.

Примеры стартовых точек:

```text
T:  (-822.3652, -795.6421, 150.709)
    (-857.5065, -738.3613, 150.709)
    ...
CT: ( 382.1349, 2102.437, -109.0)
    ( 454.8347, 2099.009, -109.0)
    ...
```

Callouts (выборка):

```text
TSpawn      (-624, -936, 120)
Middle      (-384, 1136, 60)
TopofMid    (-348, 76, 272)
BombsiteA   (1156, 2356, 176)
BombsiteB   (-1764, 2192, -4)
LongA       (1428, 1544, 124)
Catwalk     (0, 1460, 164)
MidDoors    (-384, 2036, 96)
BDoors      (-1040, 2316, 156)
```

**[FACT]** `mp_randomspawn 0` и `sv_allow_approximate_spawns 0` в
`gamemode_competitive.cfg` означают, что нельзя считать все 15 спавнов
равновероятными для 5 игроков. Наши min/median/max — это огибающая всех
стартовых точек, а не распределение назначения.

## 8. Проверка координатной системы

**[TESTED]** Все 15 T и 15 CT spawn origins лежат **внутри** nav-полигонов в
XY (distance to polygon = 0). Это подтверждает, что nav и entity origins
находятся в одной системе координат (Hammer units, Z-up).

Вертикальные смещения `origin.z - nav_plane_z(x,y)`:

| Сторона | min | median | max |
|---|---:|---:|---:|
| T | 23.69 | 29.42 | 60.08 |
| CT | 5.66 | 10.32 | 13.54 |

Это означает, что `origin` спавна не обязательно лежит точно на nav-плоскости;
для маршрута точку нужно проецировать на плоскость области, а не использовать
z сущности напрямую.

Для `env_cs_place`:

- 38 из 43 маркеров внутри nav-полигона в XY;
- 5 снаружи (например, `BombsiteB` у стены, `LongDoors`, `Hole`);
- z-смещение внутри полигона: median 118.7, max 270.0.

**[INFERENCE]** Callout origins — это маркеры в воздухе/на стене, а не точки
пола. Для маршрутов использовать XY + nav area plane/centroid, а не z маркера.

## 9. Минимальный эксперимент на `de_dust2`

### 9.1. Выбранные цели

Цели — области, выбранные по callout XY и наибольшей площади среди
содержащих полигонов:

| Цель | Area ID | Centroid (x, y, z) | Size 2D |
|---|---:|---|---:|
| Mid | 397 | (−405.3, 1056.0, −69.5) | 16 416 |
| A | 1942 | (1017.9, 2726.2, 101.5) | 6 715.1 |
| B | 1769 | (−1696.0, 2207.6, −0.5) | 36 720 |
| LongA | 1168 | (1463.0, 1625.2, −3.5) | 29 952 |
| Catwalk | 295 | (−180.3, 1015.9, 4.5) | 29 703.4 |
| MidDoors | 1308 | (−568.0, 2160.0, −119.0) | 18 432 |
| BDoors | 1651 | (−1056.0, 2336.0, −18.7) | 4 608 |

### 9.2. Метод

- Старт: каждая из 15 реальных spawn origins, спроецированная на плоскость
  своей nav-области.
- Финиш: центроид целевой nav-области.
- Маршрут: line-graph Dijkstra, стоимость — длина ломаной внутри областей;
  точки пересечения — середины **целевых** рёбер.
- Единицы: Hammer units. Время не рассчитывалось.

### 9.3. Расстояния spawn → цель

| Сторона | Цель | min | median | max | mean | stdev |
|---|---|---:|---:|---:|---:|---:|
| T | Mid | 2140.3 | 2402.3 | 2818.4 | 2440.0 | 217.4 |
| T | A | 4673.8 | 4935.8 | 5351.9 | 4973.5 | 217.4 |
| T | B | 3841.8 | 4184.9 | 4674.2 | 4229.8 | 280.9 |
| CT | Mid | 1769.3 | 2009.6 | 2208.8 | 2024.9 | 127.5 |
| CT | A | 1126.1 | 1362.1 | 1460.5 | 1324.0 | 108.5 |
| CT | B | 2189.9 | 2430.2 | 2629.3 | 2445.4 | 127.5 |

**Это расстояния, а не время.** CT-спавн центральный и ближе к обеим точкам;
T-спавн дальше. Это ожидаемое свойство обороны, а не вывод о балансе.

**[COMMUNITY]** Игрок отмечает, что путь CT → A идёт через коробки: прыжок
на коробки, затем на A plant. **[TESTED]** Для медианного CT-спавна
`movement/route.py` видит 6 vertical transitions, `+272/-49` units,
4 jump-up candidates, `J+3.0 s`; `AK 6.5–10.0 s` (continuous →
stop-at-crossings) не включает эти прыжки/приземления.

### 9.4. Разброс по спавнам

| Сторона | Цель | Range (max−min) |
|---|---|---:|
| T | Mid | 678.1 |
| T | A | 678.1 |
| T | B | 832.4 |
| CT | Mid | 439.5 |
| CT | A | 334.4 |
| CT | B | 439.4 |

**[INFERENCE]** Даже внутри одной стороны есть заметный разброс. Для
баланса нужно либо знать фактическое назначение спавнов, либо явно
моделировать худший/лучший/типичный случай. Нельзя брать один спавн как
«спавн команды».

### 9.5. Forward/reverse и one-way

Для T-маршрутов обратное направление часто длиннее:

| Маршрут | Forward median | Reverse median | Разница |
|---|---:|---:|---:|
| T → Mid | 2402.3 | 2862.0 | +459.7 |
| T → A | 4935.8 | 5415.3 | +479.5 |
| T → B | 4184.9 | 4525.6 | +340.7 |

Причина — one-way drops. Например, маршрут T → A использует
`244 -> 262` с ΔZ = −149 (в пределах `max_jump_down=157`), а обратный маршрут
вынужден идти в обход. Это не ошибка, а свойство nav.

### 9.6. Что эксперимент доказывает

**[FACT]** На реальной установленной карте можно:

1. найти nav в map VPK;
2. разобрать 2242 области и 6275 связей;
3. восстановить спавны и callouts из entity lump;
4. построить граф и найти маршруты;
5. получить стабильные расстояния и разброс по спавнам;
6. обнаружить one-way, компоненты и вертикальные аномалии.

**[INFERENCE]** Этого достаточно для технической основы проекта.

**[FACT]** Эксперимент **не** доказывает:
- время прибытия;
- баланс карты;
- проходимость с учётом collision;
- видимость;
- поведение 5 игроков;
- превосходство одной стороны.

## 10. Collision geometry: что известно

**[TESTED]** Для `de_dust2`:

```text
maps/de_dust2/world_physics.vmdl_c
size = 21 843 224 bytes
blocks:
  PHYS  offset 64       size 21 840 687
  CTRL  offset 21 840 752 size 183
  RED2  offset 21 840 944 size 1 416
  DATA  offset 21 842 368 size 856
```

**[FACT]** `world_physics.vmdl_c` — это physics-only model: почти весь файл
занимает `PHYS` block. Для сравнения:

| Карта | `world_physics.vmdl_c` |
|---|---:|
| de_dust2 | 21 843 224 |
| de_mirage | 3 494 920 |
| de_inferno | 61 274 056 |
| de_nuke | 4 693 656 |

**[FACT]** `awpy-data` использует именно `world_physics.vmdl_c`, экспортирует
его через Source2Viewer-CLI в glTF, фильтрует non-occluders и decimate-ит для
line-of-sight. Это независимое подтверждение того, что файл является
основным источником collision geometry.

**[HYPOTHESIS]** `world_physics.vmdl_c` содержит world collision и, возможно,
static prop collision. Нужно проверить экспортом: сравнить количество
треугольников/материалов с ожидаемым и наложить nav на collision.

**[FACT]** В map VPK есть 570 `vmdl_c` (агрегаты и пропы) и отдельный
`world_physics.vmdl_c`. Нельзя считать, что все 570 — collision; часть —
render/entity models.

### 10.1. PHYS block через `resourceinfo`

**[TESTED]** `resourceinfo.exe -b PHYS` на `world_physics.vmdl_c` выводит
`VPhysXAggregateData_t` как KV3-текст:

- dump: **166 123 574 байта**, **1 998 819 строк**;
- `m_parts` → `m_rnShape` → `m_hulls`;
- **10 149** блоков `m_Vertices`;
- наш streaming-парсер `tools/phys_dump_inspect.py` извлёк **10 143**
  полных hull records (6 неполных из-за состояния текстового dump);
- 9 949 hulls с collision attribute 0 (`Default`);
- 24 — attribute 1 (`ConditionallySolid`, `passbullets`);
- 16 — attribute 2 (`ConditionallySolid`, `npcclip`, `playerclip`);
- 154 — attribute 3 (`default`, `exclude player`);
- отдельные `sky`/`csgo_grenadeclip` attributes в dump есть, но hulls с ними
  среди извлечённых не встретились.

Collision attribute map:

| Index | Group | Interact as / exclude | Смысл для фильтра |
|---:|---|---|---|
| 0 | `Default` | — | мир, обычно блокирует игрока |
| 1 | `ConditionallySolid` | `passbullets` | блокирует игрока, пропускает пули |
| 2 | `ConditionallySolid` | `npcclip`, `playerclip` | player clip, блокирует игрока |
| 3 | `default` | exclude `player` | не блокирует игрока |
| 4 | `ConditionallySolid` | `csgo_grenadeclip` | граната-клип |
| 5 | `conditionallysolid` | `sky` | skybox |

Глобальные bounds hulls:

```text
x: -3860.0 .. 2573.1
y: -2200.1 .. 3876.0
z:  -216.3 ..  894.5
```

Они шире nav (skybox, крыши, внешние объекты), что ожидаемо.

**[INFERENCE]** Этих данных достаточно для **фильтрации collision по
атрибутам** и для approximate occupancy, но не для точных треугольников:
`resourceinfo` по умолчанию может усекать большие hex-блобы
(`m_VertexPositions`), а полный dump огромен. Для точной collision-геометрии
нужен VRF/Source2Viewer (PHYS → glTF) или бинарный парсер `RnHull_t`
(half-edge/face/vertex).

### 10.2. VRF export и floor test

**[TESTED]** Source2Viewer-CLI **20.1** (Windows x64, скачан в temp,
SHA-256 `67AAF8...3AA3` совпал с release asset) экспортировал
`world_physics.vmdl_c` в:

```text
world_physics_physics.gltf   57 337 bytes
world_physics_physics.bin    47 050 092 bytes
```

Содержимое:

- 39 meshes / 39 primitives / 39 materials;
- 1 306 947 vertices;
- 435 649 triangles;
- после исключения `sky` и `csgo_grenadeclip` индексируется 433 063
  треугольника;
- материалы: `physics_group_*`, `physics_passbullets_*`,
  `physics_npcclip_playerclip_*`, `physics_csgo_grenadeclip`, `physics_sky`.

**[FACT]** Локальные POSITION accessor'ы — **Hammer units, Source axes
(x, y, z-up)**. Node matrix в glTF применяет scale `0.0254` и перестановку
осей для рендера в meters/Y-up; для анализа её **нельзя** применять повторно.
Проверка на известных точках:

| Точка | Nav z | Collision z (`xyz`) | Δz |
|---|---:|---:|---:|
| T spawn | 123.33 | 116.83 | −6.50 |
| CT spawn | −122.54 | −125.44 | −2.90 |
| Mid | −69.00 | −72.40 | −3.40 |
| A | 100.91 | 97.79 | −3.12 |
| B | 0.67 | −2.12 | −2.79 |

Гипотеза `yxz` (swap X/Y) даёт на CT spawn z ≈ 8.44, то есть неверна.
Корректная конвенция — `xyz`.

**[TESTED]** Floor test: для каждой nav area взяты centroid и середины к
углам; для очень маленьких областей (<128 units²) — только centroid, чтобы
не тестировать граничные sliver-точки. Итого 8812 samples; вертикальный луч
в collision index, выбрана ближайшая горизонтальная поверхность:

| Метрика | Значение |
|---|---:|
| Samples | 8 812 |
| Match ≤ 16 units | 8 704 (98.77%) |
| Missing | 0 |
| Median \|Δz\| | 3.78 |
| P95 \|Δz\| | 9.61 |
| Max \|Δz\| | 71.0 |
| Areas with median \|Δz\| > 16 | 6 |
| Samples with \|Δz\| > 16 | 108 |

Шесть проблемных областей (`1351`, `1352`, `613`, `1104`, `1727`, `1778`)
требуют отдельного разбора. Две из них (`1351`, `1352`) — крошечные
CrouchHeight-области с Δz ≈ 71; остальные — умеренные 16–21 units. Это может
быть край геометрии, узкий проход, крыша/навес или несовпадение nav/collision.
Это не отменяет общий результат 98.77%, но должно быть в validation report.

### 10.3. Проверка стен на nav-переходах

**[TESTED]** Для каждого directed nav connection взята точка пересечения,
короткий отрезок 16 units до/после неё на высоте nav plane +24, и проверено,
пересекает ли его треугольник collision на этой высоте.

| Метрика | Значение |
|---|---:|
| Connections проверено | 6 091 |
| Пропущено vertical (>64) | 184 |
| Заблокировано | 2 (0.033%) |
| Материал | `physics_npcclip_playerclip` |

Оба флага — одна и та же reciprocal-пара `1241 <-> 1246` в районе
`(-2045.5, 465.0, 26.0)`. Это playerclip, который может быть намеренным
невидимым ограничением; требует ручной проверки, но не является массовой
ошибкой.

**Ограничение:** это не capsule sweep и не проверка лестниц/рамп; тест
проверяет только горизонтальный отрезок на одной высоте.

### 10.4. Multi-level: выше/ниже

**[TESTED]** `vertical_layers(nav, x, y)` группирует nav-плоскости в одном
XY в полосы по 8 units. На sample каждого 4-го area centroid:

| Карта | Sampled | Stacked XY | Max bands |
|---|---:|---:|---:|
| de_dust2 | 561 | 7 | 2 |
| de_nuke | 760 | 325 | 4 |
| de_vertigo | 527 | 168 | 3 |
| de_train | 539 | 26 | 2 |

Пример Nuke: в одном XY обнаружены 2–4 nav-полосы (например, верх/низ).
Vertigo использует большие абсолютные z (11492 / 11780), поэтому нельзя
предполагать, что z около нуля.

**[INFERENCE]** Для multi-level карт обязательна z-aware точка-в-области:
- выбирать область по ближайшей плоскости к player z;
- возвращать все кандидаты и флаг `ambiguous`;
- не считать, что XY определяет этаж;
- для collision floor использовать ближайшую горизонтальную поверхность,
  но сохранять другие уровни для диагностики.

3D-визуализация отложена; текущий 2.5D подход (z + layers) уже различает
верх/низ и покрыт synthetic-тестом `test_stacked_floors_are_disambiguated_by_z`.

**[TESTED]** Проверка z-aware выбора этажа на реальных spawn points:

| Карта | Spawns | Mapped | Ambiguous | Multi-band spawns | Max bands |
|---|---:|---:|---:|---:|---:|
| de_dust2 | 30 | 30 | 0 | 7 (CT) | 2 |
| de_nuke | 40 | 40 | 0 | 2 (CT) | 2 |
| de_vertigo | 30 | 30 | 0 | 0 | 1 |
| de_train | 28 | 28 | 0 | 0 | 1 |

Dust2 CT spawn: bands `[-122.5, +99.4]`, выбран `-122.5` при spawn z=-109.
Nuke CT spawn: bands `[-636, -412]`, выбран `-412` при spawn z=-404. Оба
случая подтверждают, что выбор идёт по ближайшей плоскости, а не по XY.
Ambiguous=0 потому, что этажи разнесены >64 units; для точки между этажами
`find_area_verbose` вернёт `ambiguous=true` (synthetic test).

### 10.5. Capsule clearance (point-sample)

**[TESTED]** `tools/collision_clearance_check.py`: для area samples и
connection crossing проверены:

- расстояние до ближайшей стены на высоте floor+36;
- вертикальный зазор floor → ceiling;
- clip-поверхности исключены из ceiling, но учитываются как стены.

| Метрика | Значение |
|---|---:|
| Area samples | 8 812 |
| Areas | 2 242 |
| Low ceiling (<69) | 21 |
| Narrow (<14) | 1 |
| Connections | 6 275 |
| Connection low ceiling | 14 |
| Connection narrow | 0 |
| Median gap | 199.87 |
| P05 gap | 115.78 |
| Median wall distance | 45.63 |
| Min wall distance | 13.22 |

Низкие потолки в основном находятся в CrouchHeight-областях/арках
(`114`, `115`, ...); узкая область — `1246` (13.22), та же, что playerclip
wall flag. Это требует ручной проверки, но не выглядит массовым дефектом.

**Ограничение:** point-sample, не swept capsule; проверяется одна высота
центра и вертикальный зазор, без наклона капсулы и динамических объектов.

### 10.6. Swept-capsule probe

**[TESTED]** `tools/collision_sweep_check.py`:

- crossing ± 8 units;
- waist floor+24 и head floor+55;
- radius 16, tolerance 2;
- floor mismatch >24 — отдельно.

| Метрика | Значение |
|---|---:|
| Tested | 6 091 |
| Wall flags | 516 (8.47%) |
| Path intersects wall | 384 |
| Wall within 14 | 132 |
| Low ceiling | 55 |
| CrouchHeight low ceiling | 2 |
| Floor mismatch >24 | 614 |

Flags — кандидаты на review, не доказанные ошибки: centerline капсулы не
смещается, props/дверные рамы попадают в проверку, а playerclip даёт
большую часть материалов.

### 10.7. Floor anomaly review

- `1351/1352` — CrouchHeight, nav z=-26, floor на -26 нет; concrete -132,
  playerclip 45;
- `1354` — частично тот же слой;
- `613` — tiny area 18 u², nav 143.33, concrete 123.44;
- `1104/1727/1778` — sloped areas, nav plane не совпадает с локальным
  collision floor на 16–28 units;
- `303/749/1105` — крупные рампы с локальными выбросами.

## 11. Оружие и движение

**[FACT]** `scripts/weapons.vdata_c` содержит `m_flMaxSpeed` по классам.
Ключевые значения — в [RESEARCH.md](RESEARCH.md), раздел 7.

**[TESTED]** В локальном CS2 (listen server, de_dust2, 2026-10-19) прочитаны
movement convars и измерены установившиеся скорости:

| Параметр | Значение |
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
| AK-47 / knife / AWP | 215 / 250 / 200 |
| AK walk (`Shift`) | 111.80 (= 215 × 0.52) |
| AK crouch (`Ctrl`) | 73.10 (= 215 × 0.34) |

**[FACT]** Присед не фиксированные 85: 85 = knife 250 × 0.34; для AK это
73.1. Модификатор применяется к скорости оружия.

**[FACT]** `gamemode_competitive.cfg` не содержит movement convars;
`moddefaults.txt` — dxsupport. Значения получены из running game.

Модель и ограничения: [MOVEMENT.md](MOVEMENT.md). Профиль:
`config/movement_profile.json`; код: `movement/source.py`.

## 12. Воспроизводимость

### 12.1. Хэши и артефакты

```text
de_dust2.vpk
  size   262 476 433
  sha256 51D6BB432B6553BFAE6C38219A527C5DE2464A2B107080F2B8BE7D8427EBB885

de_dust2.nav
  size   481 872
  sha256 64BBC202EDAE8A92D432368E86948BBEE3AF9C56555E190DDA251D28C64E1EA7

default_ents.vents_c
  size   45 073
  sha256 515EFDFC1E452B3D7052C5FFB1801A05E23B2395FB90586FF2DC9D14AE7EF80A

weapons.vdata_c
  size   32 731
  sha256 5CA094238E180376646A5CD69250C091AE5A9D937A3446C188EE5117FB6DA28B
```

Артефакты (не коммитятся, `.gitignore`):

```text
artifacts/nav_census.tsv
artifacts/de_dust2_experiment.json
artifacts/de_dust2_nav_routes.svg
artifacts/dust2_phys_hulls.json
artifacts/dust2_collision_floor.json
artifacts/dust2_connection_check.json
artifacts/dust2_clearance.json
artifacts/dust2_sweep_check.json
artifacts/dust2_viewer.html
```

Временные extracted-файлы:

```text
<TEMP>\cs2mb\
  de_dust2.nav
  default_ents.vents_c
  default_ents_dump.txt
  weapons.vdata_c
  weapons_vdata_dump.txt
  moddefaults.txt
  world_physics.vmdl_c
  world_physics_phys_dump.txt       # 166 MB, не коммитится
  s2v\cli\Source2Viewer-CLI.exe
  s2v\export_dust2\world_physics_physics.gltf
  s2v\export_dust2\world_physics_physics.bin
```

### 12.2. Команды

```powershell
python tools\vpk_read.py <map.vpk> list --filter .nav
python tools\vpk_read.py <map.vpk> extract maps/<map>.nav <temp>\<map>.nav
python tools\nav_inspect.py <temp>\<map>.nav --json
python tools\nav_census.py > artifacts\nav_census.tsv
python tools\nav_experiment.py <temp>\de_dust2.nav <temp>\default_ents_dump.txt `
  --json artifacts\de_dust2_experiment.json `
  --svg artifacts\de_dust2_nav_routes.svg
```

Для `resourceinfo`:

```powershell
& "<CS2_GAME>\game\bin\win64\resourceinfo.exe" `
  -game "<CS2_GAME>\game\csgo" `
  -i "<temp>\default_ents.vents_c" -all
```

**[FACT]** Все команды выше read-only. `Test-Path` не использовался.

## 13. Чего в данных нет

- Нет готовой «модели карты» в одном файле: nav, entity, collision и render
  split по разным ресурсам.
- Nav сам по себе не является collision; collision получена отдельно из
  `world_physics`. 6 проблемных floor areas классифицированы; 108 samples >16
  остаются для triage (часть — slope/nav-plane).
- Нет полной 3D-визуализации; есть 2.5D/z-aware слой.
- Нет глобальных movement convars в прочитанных конфигах.
- Нет гарантии, что `world_physics` включает все динамические двери/пропы.
- Нет вероятностного распределения назначения спавнов.
- Нет информации о фактических решениях игроков без демок/модели поведения.
- Нет оснований для выводов о балансе по расстояниям.
