# FINAL REPORT — техническая осуществимость и план

**Дата:** 2026-10-19
**Версия игры:** CS2 ClientVersion 2000933, buildid 25966348, patch 1.41.9.1
**Проверенная карта:** `de_dust2`
**Статус:** исследование завершено; реализация не начата.

> **Историческая справка:** это отчёт о feasibility-фазе от 2026-10-19. С тех
> пор реализованы importer, nav/collision-проверки, viewer, movement model,
> time-only сценарии и локальное приложение. Актуальное состояние — в
> [STATE.md](STATE.md); не читайте разделы о нереализованных пунктах как
> текущий статус.

## 1. Насколько идея реализуема технически

**Вердикт:**

| Уровень | Реализуемость | Комментарий |
|---|---|---|
| Импорт nav и построение графа | **Высокая** | Подтверждено на реальном `.nav` v36 |
| Маршруты и расстояния | **Высокая** | 2242 области, 6275 связей, устойчивые маршруты |
| Спавны, bombsite, callouts | **Высокая** | Entity lump читается, 15/15 спавнов в nav |
| Collision-проверка проходимости | **Средняя** | `world_physics.vmdl_c` с PHYS есть; экспорт и фильтрация не проверены |
| Время движения | **Средняя** | Weapon speeds есть; acceleration/friction нужно измерять |
| Симуляция 5v5 (движение) | **Средняя** | Возможна, но поведение/назначение спавнов не определены |
| Тактическая симуляция/баланс | **Низкая-средняя** | Нет модели боя/utility/видимости; нужна валидация на демках |

**Итог:** техническая основа проекта реализуема. Но это в первую очередь
**инструмент геометрического и маршрутного анализа**, а не готовый предиктор
соревновательного баланса.

## 2. Какие данные реально удалось обнаружить

**[FACT]** В установленной CS2:

- `game/csgo/maps/<map>.vpk` — self-contained VPK на карту;
- `maps/<map>.nav` — nav v36 (Dust2 481 872 байт);
- `maps/<map>/entities/default_ents.vents_c` — entity lump;
- `maps/<map>/world_physics.vmdl_c` — collision model с PHYS block;
- `maps/<map>/world.vwrld_c`, `worldnodes/n0.vwnod_c`, 570 `vmdl_c` —
  render/world/props;
- `pak01_dir.vpk` → `scripts/weapons.vdata_c` — weapon speeds;
- `game/csgo/cfg/gamemode_competitive.cfg` — round/freeze/spawn rules.

**[FACT]** Dust2:

- 632 записи в map VPK;
- 570 `vmdl_c`, 1 `nav`, 1 `vents_c`, 1 `vmap_c`, 1 `vwnod_c`;
- 2242 nav areas, 6275 edges, 0 ladders, 12 SCC, 175 one-way;
- 15 T + 15 CT spawns, 43 callouts;
- `world_physics.vmdl_c` 21 843 224 байт, PHYS 21 840 687 байт.

**[FACT]** Не найдено:

- отдельного полного `de_dust2.vphys_c` (collision в `world_physics`);
- глобальных `sv_accelerate`/`sv_friction` в прочитанных конфигах;
- готовой модели карты в одном файле.

## 3. Наиболее перспективный способ восстановления модели

**Комбинированный:**

1. `.nav` — глобальный directed graph, маршруты, расстояния, one-way, ladders.
2. `world_physics.vmdl_c` — collision geometry для пола, стен, clearance,
   видимости.
3. Entity lump — спавны, bombsite, buyzone, callouts, двери/объекты.
4. Ручные контрольные точки и in-game измерения — калибровка и проверка.
5. VRF/Source2Viewer — импорт, а не собственный полный parser Source 2.

**Почему не только nav:** nav — абстракция для ботов (radius 16, height 71),
она не гарантирует отсутствие стены, точную высоту, ширину прохода и
видимость.

**Почему не только collision:** collision не даёт готовый граф маршрутов;
нужен nav или генерация собственной сетки.

## 4. Что можно получить из `.nav` и чего не хватает

### Есть

- `area_id`, выпуклые полигоны, вершины, высоты;
- направленные связи, `edge_id`;
- one-way drops;
- `attribute_flags` (Jump, CrouchHeight, Stairs, ...);
- ladders (ID, top/bottom, direction, area refs);
- places (может быть пусто);
- movable mesh IDs/transforms;
- generation params;
- CS2 custom bot data (hiding spots и т.п.).

### Не хватает

- точной collision geometry;
- ширины/высоты прохода;
- видимости;
- динамических дверей/стекла/breakables;
- boost-позиций и части прыжков, доступных игроку;
- скоростей/ускорения/трения;
- вероятностного поведения игроков;
- семантики спавнов/bombsite (нужен entity lump).

**[FACT]** На Dust2 14 областей помечены `CrouchHeight`, 1 область имеет
нулевую 2D-площадь, 175 связей one-way. Это надо обрабатывать явно.

## 5. Какие инструменты могут восстановить геометрию и коллизии

| Инструмент | Роль | Ограничения |
|---|---|---|
| Source2Viewer / ValveResourceFormat (MIT, 20.1) | VPK, `.vmap`, `.vmdl`, `.vents`, PHYS, glTF | CLI не стабилен по аргументам; map glTF не равен collision; тяжёлый экспорт |
| ValvePak (MIT) | VPK I/O | Только VPK |
| VRF `NavMeshFile` | Полный nav parser | CLI не обязан экспортировать nav |
| Awpy (MIT, 3.1.0) | Baseline nav и demo parsing | Упрощённый nav; нет global ladders/edge_id наружу |
| cs2-nav (MIT, 0.3.20) | Rust/Python nav/visibility | Требует `.tri` collision, не читает PHYS напрямую |
| `resourceinfo.exe` (Valve) | Entity/weapon dump | Не публичный API |
| 7-Zip | — | **[TESTED]** не открывает Source 2 VPK |

**Рекомендация:** Source2Viewer-CLI + собственный nav loader; Awpy/cs2-nav —
для cross-check.

## 6. Какие параметры движения придётся измерять

**[FACT]** Из `weapons.vdata_c` уже известны max speeds:

- knife 250, C4 250;
- AK-47 215, M4A1 225, AWP 200/100, SSG08 230;
- Glock 240, Deagle 230 (есть вариант 180/220);
- grenades 245.

**Неизвестно / нужно измерить:**

- `sv_accelerate`, `sv_friction`, `sv_stopspeed`, `sv_maxspeed`;
- `sv_airaccelerate`, air control;
- jump impulse/height, crouch jump;
- walk (`+speed`) и crouch speed;
- ladder speed;
- влияние оружия/zoom на скорость;
- поведение на рампах/лестницах;
- динамические двери/пропы.

**Нельзя** подставлять community-значения как факт. `cs2-nav` constants
(250/85/800/55.83) — это **[COMMUNITY]**, полезные гипотезы для измерения.

## 7. Как проверить точность модели

1. **Целостность:** VPK CRC, nav SHA-256, `bytes_consumed == file_size`.
2. **Cross-parser:** наш nav vs VRF/Awpy: area IDs, corners, connections.
3. **Edge semantics:** reciprocal midpoint test (медиана 0 на Dust2).
4. **Координаты:** 15/15 spawns внутри nav; z-проекция на плоскость.
5. **Маршруты:** длина ≥ прямой; forward/reverse объяснимы one-way;
   synthetic fixture.
6. **Collision:** floor/wall/clearance tests; nav overlay.
7. **Движение:** локальный CS2, 10–20 повторов, сравнение с моделью.
8. **Симуляция:** инварианты, seed, Monte Carlo convergence.
9. **Баланс:** bootstrap CI, sensitivity ±10% speed/spawn/route.
10. **Регрессия:** golden JSON/hashes после обновления игры.

**Как отличить ошибку программы от данных:**

- synthetic fixture ломается → программа;
- только реальная карта → данные/координаты/collision слой;
- `bytes_consumed != file_size` → parser/layout;
- nav-связь через стену → nav/collision mismatch;
- время не сходится → movement model, не nav.

## 8. Какую архитектуру следует выбрать

**Python 3.13 + Source2Viewer-CLI + immutable Map Bundle.**

```text
CS2 (read-only)
  → ingest (Source2Viewer / resourceinfo)
  → normalize
  → Map Bundle: manifest.json, nav.json, entities.json,
                 collision.glb, metrics/*.json
  → navgraph / collision / movement
  → simulation → balance → viz
```

**Почему:**

- Python быстр для исследования и тестов;
- nav-граф мал (2–4 тыс. областей), stdlib достаточно;
- collision тяжёлый, но offline;
- C#/Rust — только если профилирование покажет bottleneck;
- полный собственный Source 2 parser не нужен.

**Границы:**

- ingest не используется в runtime;
- nav не знает о collision;
- movement не выбирает маршрут;
- simulation не читает игру;
- viz не влияет на расчёты.

## 9. Какой минимальный прототип сделать первым

**Уже частично сделан в research-скриптах:**

1. Dust2 `.nav` из map VPK.
2. Парсер 2242 областей и 6275 связей.
3. Entity dump: 15 T / 15 CT, 43 callouts.
4. Граф и маршруты T/CT → Mid/A/B.
5. SVG.
6. Диагностика: components, SCC, one-way, vertical anomalies.

**Следующий production-шаг:**

- оформить это в модули с тестами;
- добавить `world_physics` floor test;
- не добавлять время/баланс до измерений.

## 10. Какие риски могут сорвать проект

**Топ-5:**

1. Collision export окажется неполным/непригодным.
2. Не удастся измерить движение/время.
3. Симуляция 5v5 окажется недоопределённой.
4. Scope creep в combat/3D/ML.
5. Обновления CS2 ломают формат/данные.

**Менее критичные, но реальные:**

- nav слишком грубый для отдельных проходов;
- спавны назначаются не так, как мы предполагаем;
- ложная точность баланса;
- лицензионные ограничения на публикацию ассетов;
- Windows `Test-Path`.

## 11. Какие функции лучше отложить

- Combat, урон, экономика.
- Utility (smoke/molotov/flash) и их влияние.
- Полная видимость/FOV до проверки collision.
- 3D-движок/рендер.
- ML/RL поведение.
- Realtime-сервис.
- Все карты до стабилизации Dust2.
- «Единый balance score».

## 12. Пошаговый план разработки

| Этап | Результат | Класс |
|---|---|---|
| 0 | Research: nav/entities/collision inventory | done |
| 1 | Воспроизводимый importer + Map Bundle | Core |
| 2 | Nav graph + маршруты + diagnostics | Core |
| 3 | Collision floor/wall/clearance + overlay | Core |
| 4 | Измерение движения + travel time | Core |
| 5 | 5v5 движение/время | Core |
| 6 | Метрики баланса + CI + sensitivity | Core |
| 7 | Визуализация/отладка | Extension |
| 8 | Multi-map + регрессия | Extension |
| 9 | Visibility/utility/combat | Research |

Подробно — в [ROADMAP.md](ROADMAP.md).

## 13. Какие решения требуют участия пользователя

1. **Source2Viewer CLI:** разрешить скачать/распаковать Windows x64 CLI
   (≈50 МБ) в temp/tools для экспорта `world_physics.vmdl_c` и entities.
2. **CS2:** разрешить запуск локального пустого сервера для измерения
   движения (сейчас запрещено).
3. **Каталог:** переименовывать ли `cs2mapbalance` в `CS2MapBalanceLab`?
   Сейчас проект живёт в фактическом пути.
4. **Карты:** какие карты кроме Dust2 нужны в первой версии?
5. **Remote Git:** когда подключать GitHub и публиковать код (без ассетов)?
6. **Зависимости:** разрешить ли `pytest`, NumPy/SciPy, matplotlib в
   виртуальном окружении после MVP?
7. **Уровень амбиций:** нужен ли только distance/route analysis или полноценная
   5v5-симуляция с движением?

## Итоговая оценка

**Реализуемо:** да, как исследовательский инструмент маршрутов, геометрии и
временных метрик.

**Не реализуемо «из коробки»:** точный прогноз соревновательного баланса без
модели движения, поведения и валидации на реальных демках.

**Главный технический вывод:** nav + `world_physics.vmdl_c` + entities — это
достаточная основа для первого прототипа. Главный риск — не парсинг, а
**интерпретация** nav как коллизии и расстояний как времени.
