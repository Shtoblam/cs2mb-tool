# Research tools

Эти скрипты — **исследовательские**, не production-модули. Они читают файлы
CS2 только в режиме чтения и не изменяют игру.

| Файл | Назначение |
|---|---|
| `vpk_read.py` | минимальный VPK v1/v2 reader: list/extract, CRC32, chunks |
| `nav_inspect.py` | Source 2 `.nav` v30–36 parser, diagnostics, route, SVG |
| `nav_experiment.py` | Dust2 experiment: spawns/callouts → nav → distance matrix |
| `nav_census.py` | прогон всех map VPK и сводка nav-файлов |
| `phys_dump_inspect.py` | PHYS text dump → hull bounds/attributes (не полные треугольники) |
| `gltf_collision.py` | VRF physics glTF → позиции/индексы, 2D triangle index и wall segments |
| `collision_floor_test.py` | сравнение nav floor с collision floor |
| `collision_connection_check.py` | wall test на nav-переходах |
| `collision_clearance_check.py` | point-sample capsule clearance |
| `collision_sweep_check.py` | swept-capsule probe по nav-переходам |
| `auto_generate.py` | nav + entities + glTF → checks + viewer + summary + manifest |
| `prepare_map.py` | installed CS2 → nav/entities/collision → optional generation |
| `security_scan.py` | проверка tracked-файлов на personal paths/secret-like values |
| `gltf_collision_probe.py` | калибровка осей glTF по известным точкам |
| `multilevel_spawn_check.py` | z-aware проверка спавнов на multi-level картах |

## Ограничения

- `vpk_read.py` поддерживает только чтение; запись VPK не реализована.
- `nav_inspect.py` не парсит hiding spots в CustomData и не строит collision.
- `nav_experiment.py` парсит текстовый dump `resourceinfo`, а не `.vents_c`
  напрямую.
- Все скрипты используют stdlib Python 3.13; внешние зависимости не нужны.

## Примеры

```powershell
python tools\vpk_read.py <map.vpk> list --filter .nav
python tools\vpk_read.py <map.vpk> extract maps/<map>.nav <temp>\<map>.nav
python tools\nav_inspect.py <temp>\<map>.nav --json
python tools\nav_census.py
python tools\nav_experiment.py <temp>\de_dust2.nav <temp>\default_ents_dump.txt `
  --json artifacts\de_dust2_experiment.json `
  --svg artifacts\de_dust2_nav_routes.svg
python tools\collision_sweep_check.py <temp>\export_dust2\world_physics_physics.gltf `
  <temp>\de_dust2.nav --json artifacts\dust2_sweep_check.json
python tools\auto_generate.py --map de_dust2 `
  --nav <temp>\de_dust2.nav `
  --entities <temp>\default_ents_dump.txt `
  --collision-gltf <temp>\export_dust2\world_physics_physics.gltf `
  --out-dir artifacts\auto\de_dust2
```

`Test-Path` в этих командах не используется. Пути к игре и temp задаются
аргументами; скрипты не пишут в каталог игры.
