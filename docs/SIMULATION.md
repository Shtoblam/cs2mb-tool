# SIMULATION — time-only scenarios

**Статус:** первый time-only сценарий. Это не combat/5v5 balance model.

## 1. 5-man rush envelope

`simulation/scenario.py` отвечает на узкий вопрос:

> Если 5 игроков занимают 5 различных спавнов и все бегут на одну цель,
> какое распределение у median arrival time команды?

Модель:

- для каждого спавна берётся `AK a–b s` из `movement/route.py`;
- перебираются все `C(15, 5) = 3003` наборов различных спавнов;
- для каждого набора считается median low/high;
- результат — P10 / median / P90 по этим team median.

`low` — непрерывный ground run, `high` — остановка на каждом nav crossing.
Прыжки, combat, blocking и split по целям не моделируются.

## 2. Dust2, AK, 5-man rush

| Сторона | Цель | P10 low | med low | P90 low | med high | P90 high |
|---|---|---:|---:|---:|---:|---:|
| T | Mid | 10.8 | 11.3 | 12.4 | 16.7 | 18.0 |
| T | A | 22.6 | 23.1 | 24.1 | 34.2 | 35.5 |
| T | B | 18.6 | 19.6 | 21.1 | 29.7 | 31.8 |
| CT | Mid | 9.3 | 9.5 | 9.9 | 15.5 | 16.1 |
| CT | A | 6.0 | 6.5 | 6.6 | 10.0 | 10.3 |
| CT | B | 11.3 | 11.5 | 11.9 | 18.0 | 18.7 |

**[INFERENCE]** Низкий разброс CT → A объясняется тем, что все CT-спавны
близки к A по nav-маршруту. Это свойство карты и текущей модели, а не вывод
о балансе. T → A имеет заметно больший разброс.

**Важно:** CT → A содержит box jumps/vertical transitions; в таблицу они не
добавлены. Поэтому `high` для CT → A — не полное реальное время, а верхняя
граница ground/stop-go модели.

## 3. 5v5 split — assignment policies

`split_envelope` расширяет модель до фиксированного split:

```text
T:  2 A / 2 B / 1 Mid
CT: 2 A / 2 B / 1 Mid
```

Для каждого из всех `C(15,5)` наборов спавнов перебираются 30 назначений
игроков на цели. Выбирается назначение с минимальной суммой `low` times
(при равенстве — с минимальной суммой `high`). Для группы из двух игроков
arrival = median (среднее двух), для Mid — один игрок.

Это **best-case coordination**, а не поведение реальных игроков. Никакого
боя, blocking или utility нет.

| Сторона | Цель | P10 low | med low | P90 low | med high | P90 high |
|---|---|---:|---:|---:|---:|---:|
| T | Mid | 10.1 | 10.7 | 11.3 | 15.7 | 16.7 |
| T | A | 22.3 | 22.7 | 23.5 | 33.6 | 34.7 |
| T | B | 18.3 | 18.6 | 19.3 | 28.0 | 29.1 |
| CT | Mid | 8.4 | 9.1 | 9.8 | 14.9 | 16.1 |
| CT | A | 5.5 | 6.0 | 6.6 | 9.5 | 10.4 |
| CT | B | 10.8 | 11.5 | 12.1 | 17.9 | 19.2 |

**Интерпретация:** split medians ниже rush envelope, потому что назначение
оптимальное и группа может выбрать ближайшие спавны. Это не означает, что
реальная команда так сыграет.

## 4. Assignment policies

Для сравнения с optimal добавлены два seeded-политики:

- `random` — uniform choice из 30 назначений, seed=1, 8 samples/team;
- `softmax` — probability ∝ `exp(-(score - min_score)/5.0)`, seed=1,
  8 samples/team.

`softmax` — **proxy**, а не измеренная модель поведения человека. Temperature
5 seconds выбрана как явная эвристика и должна быть проверена по демкам.

| Сторона | Цель | opt low | rand low | soft low | opt high |
|---|---|---:|---:|---:|---:|
| T | Mid | 10.7 | 11.3 | 11.0 | 15.7 |
| T | A | 22.7 | 23.3 | 23.1 | 33.6 |
| T | B | 18.6 | 19.9 | 19.4 | 28.0 |
| CT | Mid | 9.1 | 9.5 | 9.5 | 14.9 |
| CT | A | 6.0 | 6.3 | 6.3 | 9.5 |
| CT | B | 11.5 | 11.6 | 11.5 | 17.9 |

**[INFERENCE]** Softmax ожидаемо ближе к optimal, чем uniform random, но это
свойство выбранной эвристики, а не доказательство поведения игроков.

## 5. Ограничения

- Split policies: optimal, uniform random, softmax proxy; real human policy
  не откалибрована.
- Нет боя, утилиты, блокировки прохода, stack.
- `J+` jump budget есть в route profile, но split/rush таблицы его не
  используют; landing/turn не откалиброваны.
- Нет динамических дверей/пропов.
- Нет калибровки по демкам.
- Выбор 5 спавнов — все сочетания, а не реальное распределение игроков.

## 5.1. Time-only balance verdict

`simulation/balance.py` compares the median low route time for every common
target:

```text
ct_advantage = mean(T_low - CT_low)
```

- `|ct_advantage| <= 1 s` → `balanced`;
- `1..3 s` CT faster → `ct_slight`;
- `>3 s` CT faster → `ct_clear`;
- symmetric T labels for negative values.

The library shows `BALANCED ±`, `CT +Ns` or `T +Ns`. This is a **route-time
heuristic**, not a combat/win-rate model. All tested alpha maps landed on the
CT side of this metric (+5.2…+14.0 s).

## 6. Тесты

`tests/test_scenario.py`:

- exact `C(15,5)` enumeration;
- zero spread при равных временах;
- single-player distribution;
- split quotas/assignments;
- optimal assignment;
- random seed reproducibility;
- softmax validation;
- two-player median;
- invalid inputs.

## 7. Следующий шаг

1. Калибровка softmax/human-like policy по демкам; сейчас temperature —
   эвристика.
2. Интегрировать `J+` jump/landing budget в split/rush и откалибровать по
   demo ticks.
3. Сравнение с demo tick arrivals.
4. Только затем — encounter/combat-модель.
