# Prototype — Dust II viewer

`dust2_viewer.py` генерирует один self-contained HTML-файл с интерфейсом
в стиле Source 2 tools:

- Source 2-style topbar, sidebar, route cards, validation card;
- beginner quick start и пояснение «что это / что не так»;
- nav-полигоны Dust2;
- 6 representative routes: T/CT → Mid/A/B;
- все spawn→target routes (Dust2 — 90) в слое `Все маршруты`
  с анимацией появления;
- route badges `↑N`/`J+...` — vertical transitions и one-airtime jump budget;
  `AK a–b s` — continuous → stop-at-crossings, без jumps (например, CT → A
  `↑6`, `J+3.0`, `6.5–10.0 s`);
- 30 spawn points;
- 7 callout/target markers;
- diagnostics (areas, edges, SCC, one-way, crouch, hull);
- distance table min/median/max + median `AK a–b s` по спавнам;
- 5-man rush envelope и split 2 A / 2 B / 1 Mid с optimal/random/softmax
  assignment (exact C(15,5), time-only);
- collision floor match, wall flags и low/narrow clearance;
- белые линии стен из collision-геометрии (29 470 сегментов, base-edge
  near-vertical triangles, clip/sky исключены);
- переключатели routes/layers, zoom, pan, fit, hover по области.

## Запуск

```powershell
python prototype\dust2_viewer.py `
  "<TEMP>\de_dust2.nav" `
  "<TEMP>\default_ents_dump.txt" `
  --collision-report artifacts\dust2_collision_floor.json `
  --connection-report artifacts\dust2_connection_check.json `
  --clearance-report artifacts\dust2_clearance.json `
  --collision-gltf "<TEMP>\s2v\export_dust2\world_physics_physics.gltf" `
  --out artifacts\dust2_viewer.html
```

Затем открыть `artifacts\dust2_viewer.html`.

## Ограничения

- Это **distance-first** прототип; `AK a–b s` — continuous → stop-at-crossings
  с измеренными accelerate/friction. Прыжки, повороты, лестницы и двери не
  учтены.
- Маршруты построены по nav, а не по collision.
- UI не является production-приложением: нет сервера, БД и авторизации.
- HTML/JSON с игровыми производными данными не коммитится (`artifacts/`).
