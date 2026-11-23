# VALIDATION — методика проверки модели и алгоритмов

**Принцип:** каждый слой проверяется независимо; ошибка парсера не должна
маскироваться ошибкой данных, а ошибка данных — ошибкой алгоритма.

## 0. Internal Source 2 engine validation (2026-11-23)

**Reference environment:** installed CS2 build `2000948`, patch `1.42.0.0`,
version date `2026-11-19`; Windows x64; Python 3.13.3; `cs2mb-source2 1.0.0`
built against ValveResourceFormat `20.1.7467`.

**Procedure:** extract `<map>.nav`, `default_ents.vents_c` and
`world_physics.vmdl_c` from each map VPK, convert entities and PHYS with the
internal engine, load the glTF with `tools/gltf_collision.py`, run
`tools/collision_floor_test.py` against the same NAV, and compare entity output
with the local `resourceinfo.exe -all` dump. The Valve dump is a
development-only reference; it is not a runtime dependency.

| Map | Primitives | Exported vertices | Triangles | Floor agreement | Median dz |
|---|---:|---:|---:|---:|---:|
| de_dust2 | 39 | 1,306,947 | 435,649 | 98.77% | 3.78 |
| de_mirage | 41 | 399,399 | 133,133 | 99.06% | 4.0 |
| de_nuke | 32 | 574,884 | 191,628 | 99.27% | 4.0 |
| de_inferno | 52 | 8,200,830 | 2,733,610 | 99.54% | 4.0 |
| de_ancient | 15 | 2,903,334 | 967,778 | 98.73% | 4.0 |
| de_train | 40 | 4,722,660 | 1,574,220 | 99.39% | 4.0 |
| de_vertigo | 37 | 631,788 | 210,596 | 99.45% | 4.0 |
| de_anubis | 34 | 2,147,526 | 715,842 | 97.34% | 4.0 |
| de_overpass | 36 | 2,654,325 | 884,775 | 97.71% | 4.0 |

Entity comparison: identical entity counts and class distributions for all nine
maps; spawn/callout/bombsite origins match after 0.01-unit text rounding. Dust2
has 415 entities, 15 T spawns, 15 CT spawns and 43 callouts.

**Synthetic cases:** empty file, garbage bytes, minimal valid header, truncated
block table, oversized declared size, unsupported header version, missing input.
All produce a controlled non-zero exit with a `cs2mb-source2:` message and no
stack trace. These run in the normal test suite when the engine is installed.

**Limits:** the real-game comparison is local and not part of CI; CI validates
the component build, synthetic resources and the Python contract. Sphere and
capsule collision is a bounded tessellation, not an exact analytic surface. A
future CS2 or ValveResourceFormat change may require revalidation.

## 1. Уровни валидации

| Уровень | Что проверяем | Критерий |
|---|---|---|
| 0. Целостность | VPK CRC, размеры, хэши, версия | файл читается, CRC/hash совпадает, `bytes_consumed == file_size` |
| 1. Парсер nav | области, полигоны, связи, ladders, generation | golden counts; нет dangling/дублей; edge semantics |
| 2. Координаты | nav ↔ entities ↔ collision | спавны внутри nav; z-проекция; glTF без лишних transform |
| 3. Граф | компоненты, SCC, one-way, аномалии | ожидаемые компоненты; аномалии объяснены |
| 4. Маршруты | кратчайший путь, длина, альтернативы | lower/upper bounds; forward/reverse; synthetic tests |
| 5. Collision | пол, стены, проходы, видимость | nav-переход не пересекает стену; floor z совпадает |
| 6. Движение | скорости, ускорение, прыжки, лестницы | модель против измерений; repeatability |
| 7. Симуляция | 5v5, время, распределение | инварианты; seed; Monte Carlo convergence |
| 8. Баланс | метрики, чувствительность | CIs; выводы не меняются от шума/одного маршрута |

## 2. Уровень 0: целостность данных

### 2.1. VPK

- Проверить magic/version/tree size/chunk index.
- Проверить CRC32 каждой записи при извлечении.
- Проверить, что `pak01_dir.vpk` ссылается на существующие chunks.
- Для map VPK — `archiveIndex == 0x7FFF` и данные внутри файла.

### 2.2. Nav

- `magic == 0xFEEDFACE`.
- `version` поддерживается (30–36).
- `area_count > 0`.
- `bytes_consumed == file_size` (наш parser уже проверяет на всех картах).
- `area_id` уникальны; connections не dangling; polygon indices валидны.
- `ladders` IDs существуют; `ladders_above/below` ссылаются на существующие
  ladders.
- SHA-256 nav совпадает с manifest.

### 2.3. Entities / collision

- Entity dump содержит ожидаемые классы: `info_player_*`, `func_bomb_target`,
  `func_buyzone`, `env_cs_place`.
- `world_physics.vmdl_c` содержит `PHYS` block; размер > 0.
- Collision glTF: triangle count > 0, bbox покрывает nav bounds с допуском.
- Hash каждого артефакта записан в manifest.

## 3. Уровень 1: парсер nav

### 3.1. Golden-тест на Dust2

Ожидаемые значения для сборки 2000933:

```text
version 36, sub_version 1, area_count 2242,
edge_count 6275, ladders 0,
components 1, SCC 12, largest SCC 2186,
crouch areas 14, zero-size areas 1.
```

Тест падает при любом расхождении, если версия игры не изменилась.

### 3.2. Независимый parser

- Сравнить area count, area IDs, corners, connections с Awpy `NavMesh` и/или
  VRF `NavMeshFile`.
- Допустимое расхождение: 0 для ID/связей; для geometry — 0 (float) или
  документированный epsilon.
- Если Awpy/VRF не читают places/ladders/generation — сравнение только по
  доступным полям.

### 3.3. Edge semantics

Проверка на reciprocal-парах:

```text
midpoint(B.edge[e_AB]) ≈ midpoint(A.edge[e_BA])
```

Порог: медиана < 1 unit, 90-й перцентиль < 5 units для чистых общих рёбер.
На Dust2 медиана 0; 4854/6100 < 20 units. Это подтверждает, что `edge_id`
относится к destination.

### 3.4. Property-based тесты

- Для каждой связи `A -> B`:
  - `B` существует;
  - `edge_id < len(B.corners)`;
  - crossing point лежит на ребре B;
  - `distance(A.centroid, crossing) > 0`.
- Для каждой reciprocal-пары: расстояние между crossing points < threshold
  (например, 20 units) **или** связь помечена как jump/drop и объяснена.
- Сумма длин рёбер > 0; нет NaN/Inf.

## 4. Уровень 2: координаты и сущности

### 4.1. Спавны

- Все spawn origins попадают в nav polygon в XY.
- Для каждого spawn: `z` отличается от плоскости nav на известную величину;
  не использовать z напрямую.
- Все 5 T и 5 CT (после назначения) имеют валидную стартовую область.
- Если spawn не найден — fail, не silently nearest.

### 4.2. Callouts

- `env_cs_place` XY внутри nav или рядом (допуск на стену/маркер).
- Callout z не используется как floor; проверка: `abs(z - plane_z)` может быть
  большой (до 270 units), это нормально.
- Для каждого callout сохранять исходный origin и snapped area.

### 4.3. Collision alignment

- Bbox collision покрывает nav bbox с допуском.
- Для набора случайных точек внутри nav area:
  - луч вниз пересекает collision floor;
  - `abs(hit_z - nav_plane_z) <= tolerance`.
- Tolerance зависит от nav erosion/step: начать с 8–16 units, затем
  откалибровать.
- Если много точек без попадания — collision export неполный или неверный
  transform.

## 5. Уровень 3: граф

### 5.1. Инварианты

- Нет duplicate area IDs.
- Нет dangling connections.
- Нет self-loops (кроме документированных).
- `degree >= 1` для областей, кроме изолированных островов.
- Компоненты: перечислить размеры; объяснить каждую (out-of-bounds, skybox,
  отдельный этаж, preview).
- SCC: перечислить; объяснить one-way drops.
- Для каждой карты: main component должна содержать спавны и bombsite; если
  нет — ошибка данных/парсера.

### 5.2. Вертикальные аномалии

Для reciprocal-связей:

```text
boundary_dz > max_jump_up + epsilon
boundary_dz < -max_jump_down - epsilon
```

- Пометить, не удалять автоматически.
- Проверить collision: есть ли ramp/boost/лестница.
- Если аномалия остаётся после ручной проверки — записать в known issues.

### 5.3. Ladders

- Количество ladders и ссылки.
- Для каждой ladder: top/bottom внутри/рядом с областями; direction валиден.
- Тест на карте с лестницей (например, Train/Mirage).

## 6. Уровень 4: маршруты

### 6.1. Синтетическая nav-сетка

Создать fixture:

```text
A - B - C
|       |
D - E - F
```

- Все areas единичные квадраты.
- Проверить:
  - путь A→F = A-B-C-F или A-D-E-F в зависимости от весов;
  - длина = 3 ребра;
  - обратный путь симметричен;
  - удаление ребра делает путь пустым;
  - one-way ребро не проходит в обратную сторону.
- Добавить/убрать область, проверить, что ID и пути не «плывут».

### 6.2. Геометрические bounds

Для реального маршрута:

```text
straight_line(start, end) <= route_length
route_length <= centroid_chain_length + epsilon
```

Второе — не строгое; если нарушено, объяснить (лабиринт/one-way). Главное:
`route_length >= straight_line`.

### 6.3. Оптимальность

- Сравнить line-graph Dijkstra с полным перебором на маленьком графе.
- Сравнить centroid Dijkstra и edge-aware Dijkstra:
  - пути могут различаться;
  - edge-aware cost должен быть <= стоимости centroid-пути, посчитанной
    edge-aware метрикой.
- Проверить, что каждый шаг пути — существующая связь.
- Проверить, что crossing points лежат на целевых рёбрах.

### 6.4. Альтернативы

- K-shortest paths (Yen) или penalty-removal:
  - альтернатива не совпадает с первым путём;
  - её длина > первой;
  - удаление первой не делает граф несвязным (если есть альтернатива).
- Метрика: `alt_distance / primary_distance`, `shared_edges`.

### 6.5. Forward/reverse

- Считать оба направления.
- Разница должна объясняться one-way/drops.
- Если разница огромна и не объяснима — проверить edge semantics/парсер.

## 7. Уровень 5: collision и проходимость

### 7.1. Floor test

- Случайные точки внутри каждой nav area.
- Raycast вниз.
- Ожидание: попадание в floor; z совпадает с плоскостью nav.
- Ошибки: дыры в collision, неверный transform, nav над пропастью.

### 7.2. Wall test

- Для каждого перехода `A -> B`:
  - взять crossing point;
  - проверить, что в окрестности нет стены, полностью перекрывающей проход;
  - проверить ширину прохода (distance transform/BVH).
- Для подозрительных переходов — raycast между центроидами A и B.
- Если стена есть, а nav-связь есть — либо nav устарел, либо collision
  содержит не тот слой (player clip/glass), либо crossing неточен.

### 7.3. Clearance test

- Для точки на маршруте: capsule/cylinder radius 16, height 71.
- Проверить пересечения с collision.
- Crouch area (flag 65536): height 35.5.
- Если капсула не проходит, а nav говорит «проход» — ошибка.

### 7.4. Ladders / drops

- Ladder: top/bottom geometry; проверить, что area refs совпадают.
- Drop: ΔZ в пределах `max_jump_down`; one-way; проверить, что обратный путь
  существует или объяснимо отсутствует.
- Jump-up: ΔZ <= `max_jump_up`; проверить collision (нет потолка).

### 7.5. Visibility (позже)

- BVH по collision.
- Проверить известные пары «видно/не видно» на Dust2.
- Сравнить с Awpy/cs2-nav, если доступен `.tri`.
- Не использовать для баланса, пока не проверено.

### 7.6. Collision floor test: фактический результат

**[TESTED]** Source2Viewer 20.1 → `world_physics_physics.gltf`:
435 649 triangles, 39 materials; после исключения sky/grenadeclip —
433 063 индексированных triangles. Для каждой nav area: centroid + середины
к углам; для областей <128 units² — только centroid. Итого 8 812 samples,
вертикальный запрос к горизонтальным поверхностям.

| Метрика | Значение |
|---|---:|
| Match ≤ 16 Hammer units | 98.77% |
| Median \|Δz\| | 3.78 |
| P95 \|Δz\| | 9.61 |
| Max \|Δz\| | 71.0 |
| Missing | 0 |
| Areas with median \|Δz\| > 16 | 6 |
| Samples > 16 | 108 |

Проверенные точки:

```text
T spawn:  nav 123.33, collision 116.83, Δz -6.50
CT spawn: nav -122.54, collision -125.44, Δz -2.90
Mid:      nav -69.00, collision -72.40, Δz -3.40
A:        nav 100.91, collision 97.79, Δz -3.12
B:        nav 0.67, collision -2.12, Δz -2.79
```

**[INFERENCE]** Систематическое отрицательное Δz около 3–6 units согласуется с
nav-аппроксимацией/эрозией, а не с ошибкой координат. 6 проблемных areas
разобраны в 7.11. Тест не доказывает полную collision-проходимость:
он проверяет только вертикальную поверхность пола.

### 7.7. Multi-level / stacked floors

**[TESTED]** `vertical_layers` на sample каждого 4-го area centroid:

| Карта | Sampled | Stacked XY | Max bands |
|---|---:|---:|---:|
| de_dust2 | 561 | 7 | 2 |
| de_nuke | 760 | 325 | 4 |
| de_vertigo | 527 | 168 | 3 |
| de_train | 539 | 26 | 2 |

Synthetic tests:

- две stacked квадратные области z=0 и z=100;
- `find_area(..., z=5)` → нижняя;
- `find_area(..., z=95)` → верхняя;
- `find_area_verbose(..., z=50, ambiguity=64)` → `ambiguous=true`,
  два кандидата;
- `vertical_layers` → две полосы [0, 100].

**Критерий:** для multi-level карт точка-в-области не должна выбирать этаж
только по XY. Если игрок между этажами, решение должно быть помечено как
неоднозначное.

**[TESTED]** Реальные spawn points:

| Карта | Spawns | Mapped | Ambiguous | Multi-band | Max bands |
|---|---:|---:|---:|---:|---:|
| de_dust2 | 30 | 30 | 0 | 7 | 2 |
| de_nuke | 40 | 40 | 0 | 2 | 2 |
| de_vertigo | 30 | 30 | 0 | 0 | 1 |
| de_train | 28 | 28 | 0 | 0 | 1 |

Dust2 CT spawn: bands `[-122.5, +99.4]`, selected `-122.5` for z=-109.
Nuke CT spawn: bands `[-636, -412]`, selected `-412` for z=-404. This is the
intended above/below behavior. `Ambiguous=0` because the floors are >64 units
apart; a point between floors triggers the synthetic ambiguity test.

### 7.8. Wall test на nav-переходах

**[TESTED]** `tools/collision_connection_check.py`: для каждого directed
connection берётся crossing point и отрезок 16 units до/после него на высоте
nav plane +24. Collision triangle index проверяет пересечение с вертикальной
стеной на этой высоте.

| Метрика | Значение |
|---|---:|
| Tested | 6 091 |
| Skipped vertical (>64) | 184 |
| Blocked | 2 (0.033%) |
| Material | `physics_npcclip_playerclip` |

Оба флага — reciprocal-пара `1241 <-> 1246` около
`(-2045.5, 465.0, 26.0)`. Это playerclip; нужна ручная проверка, является ли
ограничение намеренным.

Synthetic test `test_wall_blocks_segment_at_waist_height` проверяет, что
вертикальная стена блокирует отрезок на z=50 и не блокирует на z=150.

**Ограничение:** это не capsule sweep; проверяется одна высота, без
ступеней/рамп/лестниц.

### 7.9. Capsule clearance: point-sample

`tools/collision_clearance_check.py`:

- wall distance на высоте floor+36;
- вертикальный gap floor→ceiling;
- clip-поверхности исключены из ceiling, но учтены как стены;
- player height 71, radius 16, tolerance 2.

| Метрика | Значение |
|---|---:|
| Area samples | 8 812 |
| Low ceiling (<69) | 21 |
| Narrow (<14) | 1 |
| Connections | 6 275 |
| Connection low ceiling | 14 |
| Connection narrow | 0 |
| Median gap | 199.87 |
| P05 gap | 115.78 |
| Median wall | 45.63 |
| Min wall | 13.22 |

Низкие потолки — в основном CrouchHeight/арки; узкая область `1246`
совпадает с playerclip wall flag. Это **point-sample**, не swept capsule:
нужно ещё проверять движение капсулы по маршруту и динамические объекты.

### 7.10. Swept-capsule probe на nav-переходах

**[TESTED]** `tools/collision_sweep_check.py` — эвристический, не pass/fail.

Для каждого directed connection:

- crossing point ± 8 units вдоль направления source → target;
- два горизонтальных среза: floor+24 (waist) и floor+55 (head);
- проверяется расстояние от path до near-vertical collision-стен;
- radius 16, tolerance 2 → effective radius 14;
- вертикальный зазор проверяется в before/crossing/after;
- ceiling clip-поверхности исключены, стены — нет;
- floor mismatch >24 units считается отдельным флагом, не wall-блокировкой;
- CrouchHeight-области помечаются, но не исключаются автоматически.

| Метрика | Значение |
|---|---:|
| Tested | 6 091 |
| Skipped vertical >64 | 184 |
| Wall flags | **516** (8.47%) |
| — path intersects wall | 384 |
| — wall within 14 but not crossed | 132 |
| Low ceiling | 55 |
| Low ceiling, CrouchHeight expected | 2 |
| Floor mismatch >24 | 614 |
| Wall или non-crouch low ceiling | 543 |

Ближайший материал (не все материалы сразу):

```text
playerclip             403
metal_sand_barrel       38
wood_basket             25
sand                    22
wood_panel              15
concrete                 5
rock                     4
wood                     3
wood_plank               2
```

Примеры:

- `3 -> 4`: path на z≈34 пересекает `metal_sand_barrel` — низкий prop,
  который не виден в wall test на высоте +24;
- `2 -> 5`: playerclip на distance 13.22, то есть **tight**, а не полный
  wall intersection;
- `62 -> 199`: gap 49.76 — низкий потолок/проём;
- `114 -> 115`: на head z пересекается concrete, при этом gap 43 — это
  CrouchHeight-слой.

**Интерпретация:** 516 — это кандидаты на ручную проверку, а не 516
доказанных ошибок. Centerline капсулы не умеет смещаться вбок; nav midpoint
может быть ближе к стене, чем реальный путь игрока. Props, дверные рамы и
playerclip-объёмы входят в flags.

**Ограничение:** горизонтальный sweep на двух высотах + pointwise vertical
clearance. Это не полная 3D-капсула, не учитываются dynamic props, наклон
капсулы, ступени и возможность сместить path.

### 7.11. Разбор floor-аномалий

**[TESTED]** По `artifacts/dust2_collision_floor.json` и повторным
вертикальным запросам:

| Area | Класс | Факт |
|---:|---|---|
| 1351, 1352 | CrouchHeight / нет floor | nav z=-26; collision: concrete -132, playerclip 45; поверхности на -26 нет |
| 1354 | CrouchHeight / частично | часть samples имеет floor -29.5, часть — только ceiling 45 |
| 613 | tiny/degenerate | size 18 u², одна связь; nav 143.33, concrete 123.44 (20 ниже) |
| 1104 | ramp/nav plane | nav plane 56; collision 28.4…78.0 на разных точках |
| 1727 | ramp/nav plane | nav -63; concrete -83…-68; уклон |
| 1778 | ramp/nav plane | nav 20.67; concrete 0.47…14.14; уклон |

Вывод:

- `1351/1352` — реальное расхождение nav/collision, но это CrouchHeight-слой;
  standing route его не использует;
- `1354` — частично тот же слой;
- `613` — вероятный nav-артефакт/крошечная ledge-область, требует review;
- `1104/1727/1778` — не отдельные «дыры», а наклонные области, где одна
  nav-плоскость не описывает всю collision-поверхность;
- `303/749/1105` — крупные рампы, максимальные Δz 37–42, не median-аномалии.

Floor test остаётся полезным как coarse-проверка, но для slope/ramp-областей
нужен локальный collision floor, а не одна плоскость.

## 8. Уровень 6: движение

### 8.1. Что измерять

- max speed для knife/rifle/AWP/SSG08/pistol/grenade;
- walk (`+speed`) и crouch;
- acceleration from standstill;
- deceleration/friction;
- stop speed;
- jump impulse/height;
- crouch jump;
- ladder speed;
- zoom/alt speed;
- surface/ramp effects (если нужно).

### 8.2. Протокол измерения (после согласования)

1. Локальный пустой сервер, `sv_cheats 1`, боты выключены.
2. Фиксированный tickrate (128), стандартные настройки competitive.
3. Плоская тестовая площадка или размеченный участок карты.
4. Игрок стартует с неподвижного состояния, бежит по прямой 2–3 секунды.
5. Запись позиции/скорости по тикам (demo или `cl_showpos`).
6. Повтор 10–20 раз для каждого состояния.
7. Оценка: средняя установившаяся скорость, время до 95% max, тормозной путь.
8. Сравнить с `m_flMaxSpeed` из `weapons.vdata_c`.
9. Записать параметры и разброс в `movement_profile.json`.

### 8.3. Критерии

- Модель не должна систематически завышать/занижать время > 5–10% на
  прямолинейном маршруте.
- Для сложных маршрутов (повороты, лестницы, прыжки) — отдельная ошибка.
- Если разброс между повторами > 5%, увеличить число измерений.
- Нельзя калибровать модель по одному маршруту; нужны разные длины/углы.

### 8.4. Фактические измерения (2026-10-19)

Локальный CS2 listen server, `de_dust2`, `cl_showpos`; один прогон на
состояние, верхний туннель.

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

| Состояние | Измерено | Ожидание из файлов |
|---|---:|---:|
| AK-47 | 215.00 | 215 |
| Knife | 250.00 | 250 |
| AWP | 200.00 | 200 |
| AK walk | 111.80 | 215*0.52 |
| AK crouch | 73.10 | 215*0.34 |

Модель `movement/source.py` воспроизводит эти steady-state значения.
`tests/test_movement.py` проверяет их, `sv_maxspeed` cap, straight-line time,
jump airtime/height и монотонность. Все 19 тестов проекта проходят.

**Ограничение:** это один прогон на состояние, а не 10–20 повторов; модель
проверена на прямой, но не на поворотах/лестницах/рампах. Нужна повторная
серия по demo ticks.

## 9. Уровень 7: симуляция 5v5

### 9.1. Инварианты

- Агент не телепортируется.
- Скорость не превышает max speed + epsilon.
- Агент не проходит сквозь collision (если collision включён).
- Время монотонно.
- Seed воспроизводит тот же результат.
- Сумма агентов = 10; стороны 5/5.
- Нет одновременного занятия одной и той же позиции без правила очереди.

### 9.2. Monte Carlo

- Запуск 1000–10000 раз с разными seed/назначением спавнов.
- Оценка среднего/медианы/перцентилей времени.
- Проверка сходимости: изменение среднего < 1% при удвоении выборки.
- Чувствительность к seed.

### 9.3. Проверка поведения

- Все агенты достигают цели или явно блокированы.
- Нет «застревания» на одном месте без причины.
- Маршруты не используют запрещённые one-way в обратную сторону.
- Узкие места дают ожидаемые очереди/задержки.

## 10. Уровень 8: баланс

### 10.1. Метрики

- Время/расстояние до Mid, A, B, meeting points.
- Разница сторон (T − CT) и относительная разница.
- Разброс по спавнам (min/median/max, IQR).
- Доступность альтернативных маршрутов.
- Bottleneck score (ширина/поток).
- Sensitivity: изменение скорости ±10%, назначения спавнов, выбора маршрута.
- Не один «balance score».

### 10.2. Чувствительность

- ±10% movement speed.
- ±1–2 nav area widths (если модель позволяет).
- Удаление альтернативного маршрута.
- Изменение spawn assignment.
- Оценка: меняется ли вывод «T быстрее/медленнее» или он в пределах шума.

### 10.3. Статистика

- Bootstrap CI для медиан/разниц.
- Не сравнивать средние без распределения.
- Учитывать, что 15 спавнов — не 15 независимых наблюдений.

## 11. Синтетическая карта с известной геометрией

Два уровня:

1. **Nav fixture** (без CS2): квадраты/коридоры, известные длины, one-way,
   лестница. Быстрый unit-тест.
2. **Hammer test map** (позже, после согласования): коридор 512 units, рампа
   30°, дверь 64 units, ящик, лестница. Сгенерировать nav в CS2; проверить
   маршруты/коллизию. Изменить стену и проверить, что диагностика ловит
   изменение.

**[INFERENCE]** Nav fixture обязателен для MVP; Hammer-карта — для второго
этапа, потому что требует запуска инструментов CS2.

## 12. Регрессия

- Golden JSON: nav counts, area IDs, route snapshots, diagnostics.
- Hash игры/карты/инструмента.
- При обновлении CS2:
  1. пересобрать bundle;
  2. сравнить counts/hashes;
  3. объяснить каждое изменение;
  4. обновить golden с review.
- Не обновлять golden автоматически.

## 13. Как отличить ошибку программы от неточности данных

| Симптом | Вероятная причина | Проверка |
|---|---|---|
| `bytes_consumed != file_size` | parser/layout | сравнить с VRF/Awpy; проверить версию |
| dangling connection | parser или битый nav | проверить area IDs; cross-parser |
| spawn не в nav | coordinate/transform | проверить XY, plane, единицы |
| nav-связь через стену | nav устарел / collision слой / crossing | raycast, visual, material groups |
| route length < straight | ошибка метрики/координат | проверить точки, единицы |
| forward/reverse huge | one-way или edge semantics | список one-way, crossing points |
| floor z mismatch | nav erosion/step или collision filter | распределение ошибок, tolerance |
| время не сходится | movement model или маршрут | измерить скорость/ускорение, сравнить траекторию |
| баланс «переворачивается» | шум/выбор спавна/маршрута | sensitivity, CI |

**Правило:** если ошибка воспроизводится на синтетическом fixture — это
программа. Если только на реальной карте — сначала проверить данные и
coordinate transform, затем collision слой, затем модель.

## 14. Критерии приёмки MVP

- [ ] Dust2 bundle собран, manifest/hashes записаны.
- [ ] Nav parser проходит golden и cross-parser.
- [ ] 15/15 T и 15/15 CT спавнов найдены в nav.
- [ ] Маршруты T/CT → Mid/A/B построены, длины воспроизводимы.
- [ ] Forward/reverse различия объяснены.
- [ ] Диагностика: components, SCC, one-way, vertical anomalies.
- [x] Collision glTF получен; floor test 98.77% ≤16 units (Dust2).
- [x] Multi-level z-aware lookup покрыт synthetic test.
- [x] Wall test выполнен: 6091 connections, 2 playerclip flags.
- [x] Point-sample capsule clearance выполнен: 21 low ceiling, 1 narrow.
- [x] Swept-capsule probe выполнен (516 flags, требует triage); LOS — нет.
- [x] 6 проблемных collision areas разобраны/классифицированы; 108 samples >16
  остаются для triage.
- [ ] Нет утверждений о времени/балансе без измерений.
- [ ] Все тесты запускаются одной командой.
