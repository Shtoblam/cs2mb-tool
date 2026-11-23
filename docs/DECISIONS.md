# DECISIONS — принятые решения и причины

Формат: ADR (Architecture Decision Record). Статус: `accepted`, `proposed`,
`rejected`, `superseded`.

## ADR-001. Источник истины — установленная CS2, read-only

**Статус:** accepted.

**Контекст:** нужны реальные nav, entities, collision и версия игры.

**Решение:** читать файлы установленной CS2 только в режиме чтения; не
изменять, не запускать CS2 на этапе исследования; все производные данные
хранить вне каталога игры.

**Последствия:**

- версия игры фиксируется в manifest;
- при обновлении CS2 bundle пересобирается;
- нельзя «подправить» ресурс в игре;
- нужен read-only VPK/парсер или Source2Viewer.

## ADR-002. Nav — основной граф маршрутов, collision — отдельный слой

**Статус:** accepted.

**Контекст:** nav даёт готовую топологию, но является абстракцией для ботов.

**Решение:** использовать `.nav` для глобального графа и маршрутов;
использовать `world_physics.vmdl_c`/collision для проверки пола, стен,
clearance и видимости.

**Последствия:**

- два независимых слоя и два набора тестов;
- нельзя «выводить» collision из nav;
- маршрут может быть валиден по nav, но заблокирован по collision — это
  диагностируется, а не игнорируется.

## ADR-003. Не писать полный парсер Source 2

**Статус:** superseded by ADR-018 (2026-11-23). Историческое решение сохранено.

**Контекст:** Source 2 resource formats сложны; VRF уже покрывает VPK,
vmap/vmdl/vents/PHYS, glTF.

**Решение:** использовать Source2Viewer-CLI/ValvePak/VRF для импорта.
Собственный код — только узкий read-only `.nav` loader и промежуточная модель.

**Последствия:**

- меньше риска ошибок формата;
- зависимость от внешнего CLI и его версии;
- CLI нужно pin-ить и оборачивать тестами;
- для production можно перейти на C# VRF library.

## ADR-004. Python + stdlib для исследования, Source2Viewer — внешний импорт

**Статус:** superseded by ADR-018 (2026-11-23). Python + stdlib остаётся для
анализа; внешний Source2Viewer больше не является runtime-зависимостью.

**Контекст:** нужна быстрая итерация; nav-граф мал (2–4 тыс. узлов).

**Решение:** Python 3.13, stdlib для VPK/nav/графа/метрик; Source2Viewer CLI
для тяжёлого импорта; NumPy/SciPy только после профилирования.

**Последствия:**

- быстрый старт, простые тесты;
- collision может потребовать NumPy/C#/Rust позже;
- минимум зависимостей.

## ADR-005. Промежуточный Map Bundle вместо повторного разбора VPK

**Статус:** accepted.

**Контекст:** повторный экспорт 21–61 МБ collision и разбор VPK медленный.

**Решение:** один раз собирать bundle: `manifest.json`, `nav.json`,
`entities.json`, `collision.glb`, `metrics/*.json`; анализ работает только с
bundle.

**Последствия:**

- воспроизводимость и скорость;
- нужно версионирование схемы;
- bundle не коммитится (игровые данные);
- при обновлении игры — новый bundle.

## ADR-006. Edge-aware line-graph routing

**Статус:** accepted.

**Контекст:** centroids дают грубую длину; `edge_id` позволяет точнее.

**Решение:** строить состояния `(previous_area, current_area)`, стоимость —
расстояние между точкой входа и выхода внутри выпуклой области; точки
пересечения — середины целевых рёбер.

**Последствия:**

- точнее длина и маршрут;
- больше состояний (≈6–10 тыс.), но всё ещё быстро;
- нужна проверка edge semantics (сделана);
- one-way связи обрабатываются естественно.

## ADR-007. Не выдавать время без измеренной модели движения

**Статус:** accepted.

**Контекст:** в игре есть weapon speeds, но нет глобальных acceleration/friction
в прочитанных конфигах; community-значения не подтверждены.

**Решение:** на первом этапе выдавать только расстояния и явно это указывать.
Время — после измерения в локальном CS2.

**Последствия:**

- меньше ложной точности;
- нужен этап измерений и согласование запуска CS2;
- метрики баланса на первом этапе — distance-first + ideal straight-line
  time как нижняя оценка.

## ADR-008. Не использовать vanity/preview VPK

**Статус:** accepted.

**Контекст:** vanity-карты усечены и не содержат nav; preview-nav может иметь
0 областей.

**Решение:** брать только `game/csgo/maps/<map>.vpk` с `area_count > 0` и
nav version 30–36.

**Последствия:**

- меньше ложных ошибок;
- список карт нужно фильтровать.

## ADR-009. Не коммитить игровые ресурсы и не подключать remote Git сейчас

**Статус:** superseded (в части remote; см. ADR-016).

**Контекст:** ресурсы Valve; пользователь запретил публикацию и remote без
согласования.

**Решение:** `.gitignore` для `data/`, `artifacts/`, `*.vpk`, `*.nav`, `*.dem`,
`*.glb`; remote не добавлять.

**Последствия:**

- репозиторий содержит только код/документы;
- артефакты воспроизводятся локально;
- remote — отдельный этап.

## ADR-010. Nav — не точная collision; все выводы помечать уровнем

**Статус:** accepted.

**Контекст:** nav generated for radius 16/height 71, may omit player-possible
boost/edge cases; one-way drops.

**Решение:** в отчётах всегда указывать, основан ли вывод на nav, collision,
движении или симуляции; не смешивать.

**Последствия:**

- честная интерпретация;
- больше документации;
- меньше риска ложных выводов о балансе.

## ADR-011. 5v5 MVP — только движение и время, без боя

**Статус:** proposed (ожидает согласования).

**Контекст:** бой/экономика/utility требуют данных и моделей, которых нет.

**Решение:** первый симулятор — 10 агентов, маршруты, время, встречи,
bottlenecks; без стрельбы и урона.

**Последствия:**

- проверяемая база;
- тактические выводы ограничены;
- combat — отдельный research-этап.

## ADR-012. Z-aware point location и multi-level

**Статус:** accepted.

**Контекст:** Nuke/Vertigo/Train имеют несколько nav-этажей в одном XY;
Dust2 тоже содержит stacked-области (7/561 sampled, max 2 bands).

**Решение:** точка-в-области всегда учитывает z:
- `area_candidates` возвращает все области, содержащие XY;
- `find_area` выбирает ближайшую плоскость, а не только centroid;
- `find_area_verbose` возвращает кандидатов и флаг `ambiguous`;
- `vertical_layers` группирует этажи в полосы;
- collision floor выбирает ближайшую горизонтальную поверхность, но
  сохраняет другие уровни для диагностики.

**Последствия:**

- нельзя считать XY однозначным этажом;
- synthetic test на stacked floors обязателен;
- 3D-визуализация не требуется для корректного выбора этажа, но полезна
  в будущем.

## ADR-013. Координаты VRF physics glTF

**Статус:** accepted.

**Контекст:** VRF 20.1 экспортирует physics glTF с node matrix, которая
масштабирует в meters и переставляет оси. Локальные POSITION accessor'ы при
этом остаются в Hammer units/Source axes.

**Решение:** для анализа использовать локальные POSITION напрямую
(конвенция `xyz`), игнорировать node matrix. Проверять конвенцию на известных
точках (T/CT/Mid/A/B) до массовых запросов.

**Последствия:**

- нельзя применять `0.0254` повторно;
- floor test совпал с nav на 98.77% в пределах 16 units;
- при обновлении VRF нужно повторить калибровку.

## ADR-014. Source2Viewer CLI 20.1 и 3D

**Статус:** superseded by ADR-018 (2026-11-23). Историческое решение сохранено.

**Контекст:** для collision нужен PHYS → glTF; Source2Viewer CLI — проверенный
путь. 3D-визуализация полезна, но не приоритет.

**Решение:** использовать pinned Source2Viewer CLI 20.1 из temp (SHA-256
проверен), не добавлять его в Git. 3D-визуализацию отложить; сначала
2.5D/z-aware UI и проверка этажей.

**Последствия:**

- collision export воспроизводим;
- CLI не является runtime-зависимостью;
- 3D можно добавить без переделки ядра.

## ADR-015. Windows path safety

**Статус:** accepted.

**Контекст:** известная проблема с `C:\Windows\System32\Test-Path` (0 байт).

**Решение:** никогда не вызывать неквалифицированный `Test-Path`; в
PowerShell — `[System.IO.File]::Exists` / `[System.IO.Directory]::Exists`; в
Python — `pathlib.Path.exists()`.

**Последствия:**

- скрипты безопасны;
- нельзя копировать сторонние PowerShell-сниппеты без проверки;
- при ошибке — фиксировать точный текст, не менять системные файлы.

## ADR-016. Remote Git origin подключён

**Статус:** accepted.

**Контекст:** пользователь создал приватный репозиторий
`https://github.com/Shtoblam/cs2mb-tool.git` и разрешил подключение.

**Решение:** `origin` добавлен, `main` отслеживает `origin/main`; push
выполняется обычным `git push` без force. Игровые ресурсы и секреты
по-прежнему не публикуются.

**Последствия:**

- локальные коммиты синхронизированы с `origin/main`;
- история линейная, force push запрещён;
- при расхождении — разбираться, не перезаписывать remote.

## ADR-017. Movement profile измерен в локальном CS2

**Статус:** accepted.

**Контекст:** movement convars отсутствуют в прочитанных cfg; community-
значения расходятся (crouch 85 vs AK 73.1, freeze 20 vs 15).

**Решение:** запустить локальный listen server, прочитать convars и измерить
steady-state через `cl_showpos`; сохранить
`config/movement_profile.json`; реализовать Source-style модель в
`movement/source.py`; для crouch ниже `sv_stopspeed` использовать effective
`friction_floor = min(stopspeed, target_speed)`.

**Последствия:**

- AK/knife/AWP/walk/crouch воспроизводятся;
- измерения одиночные, нужна повторная серия по demo ticks;
- time применим только к прямой; повороты/лестницы/рампы ещё не учтены;
- нельзя использовать фиксированные 85 для crouch всех оружий.

## ADR-018. First-party internal Source 2 engine instead of a runtime CLI

**Статус:** accepted (2026-11-23). Supersedes ADR-003, ADR-004 and ADR-014.

**Контекст:** automatic map processing required Source2Viewer-CLI for PHYS →
glTF and `resourceinfo.exe` for the entity dump. Both are external runtime
utilities; a fresh installation could not process a map without them.

**Решение:** build a first-party `cs2mb-source2` component from `sri/`.
It links the pinned MIT ValveResourceFormat 20.1.7467 library in-process for
binary KV3, Zstandard/LZ4, PHYS and EntityLump decoding and exposes a small
CS2MB-specific command line (`phys`, `entities`, `inspect`, `phys-summary`).
The Python application reaches it through `tools/source2.py` with argument
arrays, explicit paths and timeouts. The component is published as a
self-contained Windows x64 executable; no .NET runtime or external CLI is
required at runtime.

**Последствия:**

- Source2Viewer-CLI and `resourceinfo.exe` are no longer runtime dependencies;
- the Python analysis layer remains stdlib-only;
- the component is a trusted local executable and must be hash-verified;
- a future Valve resource-format change may require rebuilding the component;
- upstream MIT attribution and license notices are shipped with the asset.

## ADR-019. Preserve the existing collision and coordinate contract

**Статус:** accepted (2026-11-23).

**Контекст:** the existing collision loader expects glTF accessor positions in
Hammer units and Source axes, ignores the node matrix, and filters primitives by
material/InteractAs. A new exporter could silently double-transform geometry.

**Решение:** emit one primitive per collision-attribute × surface-property
group; write positions in Hammer units/Source axes (`x`, `y`, `z-up`); apply
the PHYS bind pose once; omit the legacy render-time `meters/Y-up` node matrix.
Preserve `InteractAs`, `SurfaceProperty` and `CollisionGroup` metadata and the
existing material naming semantics.

**Последствия:**

- `tools/gltf_collision.py` and all downstream algorithms remain unchanged;
- the historical Dust2 totals are reproduced exactly (39 primitives,
  1,306,947 exported vertices, 435,649 triangles);
- floor agreement remains 98.77% at the historical tolerance;
- the converter must be revalidated if the coordinate contract changes.

## ADR-020. Keep the entity dump text contract

**Статус:** accepted (2026-11-23).

**Контекст:** the project already has a line-oriented entity-dump parser used by
navigation, spawn and callout logic. Replacing it with a new JSON contract would
expand the change surface and risk behavioural drift.

**Решение:** `cs2mb-source2 entities` emits the existing text shape with
`key = value`, quoted strings, array values and the classname/targetname/
place_name/origin keys ordered first. All entity properties and connections are
preserved, not only the currently displayed fields.

**Последствия:**

- existing `parse_entity_points` and auto-generation consumers stay unchanged;
- Dust2 entity output matches the local `resourceinfo` dump semantically
  (415 entities, 15 T/15 CT spawns, 43 callouts, identical origins);
- the text contract is a compatibility boundary and needs golden tests.

## ADR-021. Bounded tessellation for curved collision primitives

**Статус:** accepted (2026-11-23; revised after nine-map validation).

**Контекст:** the first implementation rejected spheres and capsules to avoid
silent geometry loss. Nine-map validation showed that `de_anubis` (52 capsules)
and `de_overpass` (13 spheres, 524 capsules) use them, so rejection made two
supported maps unprocessable.

**Решение:** tessellate sphere and capsule primitives with bounded, deterministic
ring counts (16 radial segments; 10 sphere rings; 5 hemisphere rings per capsule
end), transform the generated points once by the part bind pose, skip degenerate
triangles, and keep mesh/convex-hull geometry exact. Invalid centers/radii are
reported as controlled errors. Curved surfaces are analysis approximations, not
exact analytic collision.

**Последствия:**

- all nine active-duty maps process successfully;
- curved primitives add triangles but no silent loss of collision shapes;
- the approximation is documented in setup, architecture and security docs;
- future work may replace tessellation with exact distance queries if the
  collision layer needs them.

## ADR-022. Component distribution and provenance

**Статус:** superseded by ADR-024 (2026-11-23). Historical decision preserved.

**Контекст:** the component is a binary and must not be committed to Git or
downloaded automatically at map-processing time.

**Решение:** publish a versioned `cs2mb-source2-win-x64.zip` release asset with
the executable, MIT license and third-party notices, plus `SHA256SUMS.txt`.
Users install it into `tools/bin/sri/` or set `CS2MB_SOURCE2`. The
preparation manifest records the engine path, version and SHA-256. Normal
processing is offline; the application does not fetch updates.

**Последствия:**

- the binary stays out of Git;
- installation requires one explicit download from the CS2MB release page;
- users can reproduce the build with `sri/build.ps1` and the pinned SDK and
  package versions;
- a stale override fails loudly instead of falling back silently.

## ADR-023. Rename the internal component to SRI

**Статус:** accepted (2026-11-23).

**Контекст:** the component was introduced as `cs2mb-source2`. That name
described the input format but not the component's role, and it conflicted with
Valve's Source 2 terminology in user-facing text.

**Решение:** the component is **SRI — Source Resource Inspector**. The
executable is `cs2mb-sri.exe`; the source lives in `sri/`; the Python wrapper is
`tools/sri.py`; the environment variable is `CS2MB_SRI`; the CLI override is
`--sri`; server fields are `sri_ready`, `sri_version` and `sri_sha256`.
The parent product remains CS2 Map Balance / CS2MB.

**Последствия:**

- all current runtime, UI, API, documentation, build and release references use
  SRI;
- historical notes that mention `cs2mb-source2` remain labelled historical;
- PHYS/EntityLump behaviour and coordinate contracts are unchanged;
- SRI is a resource inspector/converter, not a universal Source 2 viewer.

## ADR-024. One complete CS2MB release

**Статус:** accepted (2026-11-23). Supersedes ADR-022.

**Контекст:** the separate `source2-v1.0.0` component release made users assemble
the application from multiple downloads.

**Решение:** publish one complete Windows x64 package containing the application,
SRI, portable Python 3.13, launchers, documentation, `SHA256SUMS.txt` and an
SPDX SBOM. The old standalone engine release is removed only after the complete
release is published and verified.

**Последствия:**

- one primary user download;
- no manual SRI conversion step;
- no Python installation for packaged users;
- the complete archive must be extracted and tested before publication;
- checksums and SBOM are part of the release gate.

## ADR-025. Security hardening for the complete release

**Статус:** accepted (2026-11-23).

**Контекст:** the backlog listed unbounded jobs, incomplete process-tree
termination, endpoint test gaps, missing Host checks and unsafe remote binding.

**Решение:** implement a two-job limit with `429` rejection, prune stale job and
upload records, terminate the full Windows process tree on timeout, add direct
endpoint tests, enforce a loopback Host allow-list and same-origin POST checks,
reject `--allow-remote`, clean rejected uploads and redact personal absolute
paths from preparation manifests.

**Последствия:**

- P1 backlog items are closed;
- P2 endpoint and Host/CSRF items are addressed by runtime tests;
- remote access is intentionally unsupported;
- remaining viewer-content and code-signing items stay in the backlog;
- no security claim beyond the tested local threat model.

## ADR-026. Original logo is the canonical visual identity

**Статус:** accepted (2026-11-23).

**Контекст:** the previous visual pass introduced an invented vector mark that
did not faithfully represent the owner's original `logo.png`.

**Решение:** preserve the existing root `logo.png` unchanged as the canonical
CS2MB identity. Remove invented logo variants. Use the original PNG in the
application, website, README and social preview. Technical SVG illustrations may
contain no invented brand mark; where a banner or social image needs the logo,
embed the original PNG faithfully. The favicon is the original PNG.

**Последствия:**

- the owner's identity is preserved byte-for-byte;
- no alternative monogram or navigation-symbol logo remains;
- screenshots and social assets must use the original image;
- SVG diagrams are information graphics, not logo substitutes.
