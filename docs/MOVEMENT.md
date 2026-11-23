# MOVEMENT — измеренные параметры и модель движения

**Дата измерения:** 2026-10-19
**Игра:** CS2 ClientVersion 2000933, buildid 25966348, patch 1.41.9.1
**Сервер:** локальный listen server, `de_dust2`
**Файлы игры:** не изменялись; CS2 запускался и был закрыт после замеров.

> **Provenance / актуальность:** это исторические измерения указанной сборки.
> В maintenance-проверке 2026-11-21 установленный `appmanifest` сообщал build
> `26798866`; значения движения не перемерялись. Не переносите эти числа на
> другую сборку без повторной калибровки.

## 1. Метод

1. CS2 запущен windowed с `-console -condebug`.
2. В консоли прочитаны movement convars.
3. Игрок телепортирован в верхний туннель Dust2:
   `setpos -1665 700 40`, `setang 0 90 0`.
4. `cl_showpos 1`; удерживался `W` 1.6–2.6 с.
5. Считывалась установившаяся `vel` из HUD.
6. Для оружия использовались `give weapon_*` и `slot1/slot3`.
7. Для приседания удерживался `Ctrl`, для ходьбы — `Shift`.

Это одиночные прогоны, а не статистически строгая серия. Значения
`cl_showpos` округлены до 0.01; перед финальной калибровкой нужно повторить
замеры по тикам демо.

## 2. Прочитанные convars

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

`sv_walkspeed` и `sv_crouchspeed` как отдельные convars не найдены; модификаторы
измерены через фактическую скорость.

## 3. Установившиеся скорости

| Состояние | Измерено | Комментарий |
|---|---:|---|
| AK-47 | 215.00 | совпадает с `m_flMaxSpeed=215` |
| Knife | 250.00 | совпадает с `m_flMaxSpeed=250` |
| AWP | 200.00 | совпадает с `m_flMaxSpeed=200` |
| AK-47 walk (`Shift`) | 111.80 | `215 * 0.52` |
| AK-47 crouch (`Ctrl`) | 73.10 | `215 * 0.34` |

Важно: **присед не является фиксированными 85 units/s**. 85 — это
`knife 250 * 0.34`. Для AK присед — 73.1. Модификатор надо применять к
максимальной скорости оружия.

## 4. Модель

Реализация: `movement/source.py`.
Профиль: `config/movement_profile.json`.

Использованы формулы Source SDK:

```text
friction:
  control = max(speed, friction_floor)
  drop = control * sv_friction * surface_friction * dt
  newspeed = max(0, speed - drop)

accelerate:
  addspeed = wishspeed - velocity
  accelspeed = sv_accelerate * dt * wishspeed * surface_friction
  velocity += min(accelspeed, addspeed)
```

`wishspeed = min(weapon_max_speed, sv_maxspeed) * modifier`.

Особенность CS2: присед AK (73.1) ниже `sv_stopspeed=80`, поэтому классическая
формула Source с `control=sv_stopspeed` не выходит на 73.1. В модели
используется `friction_floor = min(sv_stopspeed, target_speed)`, откалиброванный
по измерению. Это **effective model**, а не утверждение о внутреннем коде CS2.

## 5. Straight-line результаты

Для AK-47, старт с нуля, `dt=1/128`, без препятствий:

| Дистанция | Время | Средняя скорость |
|---:|---:|---:|
| 100 | 0.641 s | 158.51 |
| 500 | 2.500 s | 200.53 |
| 1000 | 4.820 s | 207.49 |
| 2000 | 9.477 s | 211.18 |
| 4000 | 18.773 s | 213.07 |

Это **идеальная прямая**; реальный маршрут медленнее из-за поворотов,
лестниц, дверей, прыжков и столкновений.

### 5.1. Route vertical profile

`movement/route.py` считает для 3D-полилинии:

- `vertical_up` / `vertical_down`;
- `vertical_transitions` — сегменты с `|Δz| > max_climb (16)`;
- `max_rise` / `max_drop`;
- `turn_count` / `max_turn_deg`;
- `ideal_time` — straight-line модель по полной 3D-длине;
- `stop_go_time` — сумма straight-line прогонов по каждому сегменту с нулевой
  скоростью на каждом nav crossing;
- `jump_up_candidates` — подъёмы `16 < dz <= 68` с horizontal ≤64;
- `ramp_rises` — более длинные/высокие подъёмы, не отнесённые к jump;
- `jump_budget` — `jump_up_candidates × 0.755 s` (measured airtime);
- `time_high_with_jumps` — `stop_go_time + jump_budget`.

В UI показывается диапазон `AK a–b s`:

- `a` — `ideal_time`: непрерывный ground run, нижняя граница;
- `b` — `stop_go_time`: остановка на каждом crossing, верхняя граница;
- реальное время скорее между ними; range не включает прыжки/приземления.

**Важно:** `vertical_transitions` — это вертикальные переходы (рампы,
ступени, ledges, box jumps), а не обязательно ровно N прыжков.

**[COMMUNITY]** Игрок отмечает, что путь CT → A идёт через коробки: запрыгнуть
на коробки, затем на A plant. **[TESTED]** Для медианного CT-спавна маршрут
до A имеет 6 vertical transitions, `+272 / -49` units, 4 jump-up candidates,
`J+3.0 s` и `AK 6.5–10.0 s`; `high + budget ≈13.0 s`. Это всё ещё не
измеренное время маршрута. В UI route cards получают badge `↑N` и `J+...`
с tooltip.

Другие representative routes: T B `J+1.5`, CT B `J+0.8`; T A/T Mid/CT Mid
не имеют коротких jump-up candidates (их подъёмы классифицированы как ramp).

Диапазоны representative routes:

| Маршрут | AK, s |
|---|---:|
| T → Mid | 11.3–16.7 |
| T → A | 23.1–34.2 |
| T → B | 19.6–29.7 |
| CT → Mid | 9.5–15.0 |
| CT → A | 6.5–10.0 |
| CT → B | 11.5–17.5 |

## 6. Прыжок

Из `sv_jump_impulse=301.993` и `sv_gravity=800`:

```text
airtime = 2 * 301.993 / 800 = 0.7549825 s
height  = 301.993^2 / (2 * 800) = 56.9999 units
```

Это теоретические значения для вертикального прыжка без учёта step/air
control. HUD `cl_showpos` показывал `jump: 0.000 (39.62)`; это поле не
использовалось как высота прыжка без отдельной расшифровки.

## 7. Ограничения

- Нет поворотов, ускорения при смене направления.
- Нет рампов, ступеней, лестниц, воздуха.
- Нет дверей, стекла, динамических пропов.
- Нет проверки на демо-тиках.
- Одиночные прогоны; нужна повторяемость.
- CS2 может отличаться от Source 1 в деталях friction/acceleration.
- `sv_maxspeed=320` — cap; оружие имеет меньшие скорости.

## 8. Воспроизведение

```text
sv_cheats 1
mp_warmup_start
bot_kick
cl_showpos 1
setpos -1665 700 40
setang 0 90 0
give weapon_ak47
```

Затем удерживать `W`; для walk — `Shift+W`, для crouch — `Ctrl+W`.

## 9. Тесты

`tests/test_movement.py`:

- AK/knife/AWP steady-state;
- walk/crouch;
- `sv_maxspeed` cap;
- straight-line time > naive distance/speed;
- jump airtime/height;
- monotonic distance.

`tests/test_route.py`:

- flat route совпадает со straight-line моделью;
- rise + right turn + jump budget;
- drop считается отдельно;
- long rise классифицируется как ramp, не jump.

`tests/test_scenario.py`:

- exact `C(15,5)` team enumeration;
- zero spread при равных временах;
- single-player / split quotas;
- optimal assignment / two-player median;
- random seed reproducibility / softmax validation / invalid inputs.

Текущий набор проекта содержит 56 unit tests; он проходит на `main`. Это
unit-проверки модели и парсеров, а не валидация движения по demo ticks.
