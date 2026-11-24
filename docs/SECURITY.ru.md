# SECURITY — v1.1.0

**Область:** локальный `app/server.py`, auto-generation pipeline, SRI (`sri/`),
`tools/sri.py`, пользовательские файлы и release packaging.

## Что приложение не делает

- не запускает CS2/Steam;
- не читает память игры;
- не взаимодействует с anti-cheat;
- не подключается к игровым серверам;
- не выполняет загруженный код;
- не отправляет телеметрию или файлы наружу;
- не пишет в каталог игры;
- не требует администратора/root.

Приложение можно использовать при полностью закрытой CS2. Viewer —
self-contained HTML без внешнего JS/CSS/трекеров. HTTP-сервер слушает только
`127.0.0.1`.

## Аудит VAC / anti-cheat

Дата: **2026-11-23**. Проверены `app/server.py`, `app/index.html`,
`tools/prepare_map.py`, `tools/sri.py`, `sri/`, `tools/auto_generate.py`,
viewer, packaging scripts, оба GitHub Actions workflow и runtime-модули.

Результат: **взаимодействия с VAC не найдено**. Это статический обзор кода,
зависимостей и release-конфигурации, а не сертификация безопасности.

- нет `cs2.exe`/`steam.exe`, перечисления процессов и attach;
- нет `OpenProcess`, `ReadProcessMemory`, `WriteProcessMemory`,
  `CreateRemoteThread`, `VirtualAllocEx`, DLL-инъекций и хуков;
- нет оверлея, автоматизации ввода, консольных команд и участия в матче;
- нет связи со Steam, игровыми серверами, VAC или внешним API;
- нет доступа к памяти игры и записи в каталог игры;
- не нужен администратор/root;
- дочерние процессы: локальный Python pipeline и SRI; Valve diagnostic tool и
  Source2Viewer-CLI не запускаются.

**Это не абсолютная гарантия:** Valve может изменить правила. Утверждение
относится к этому коду и перечисленным зависимостям.

## SRI — Source Resource Inspector

SRI собирается из `sri/` и подключает MIT-библиотеку ValveResourceFormat
`20.1.7467` в процессе. Он разбирает binary KV3, Zstandard/LZ4, PHYS и
EntityLump, не скачивает обновления, не ходит в сеть и не подключается к CS2.
SRI входит в полный пакет CS2MB; отдельный конвертер не требуется.

SRI — локальный доверенный бинарник. Сверяйте SHA-256 с `SHA256SUMS.txt`.
`prepare_map.py` записывает путь, версию и SHA-256 в `prepared_manifest.json`.
Устаревший `CS2MB_SRI`/`--sri` приводит к ошибке, а не к молчаливому выбору
другого exe.

## Внешние runtime-инструменты

Source2Viewer-CLI и `resourceinfo.exe` не ищутся и не запускаются приложением.
Upload-режим по-прежнему принимает подготовленные `.gltf`/`.bin` и entity text.

## Модель угроз

- произвольное чтение локальных файлов через path API;
- CSRF с внешнего сайта на localhost;
- traversal в именах файлов и sidecar;
- исчерпание ресурсов огромными/повреждёнными ресурсами;
- ошибки границ при разборе PHYS/EntityLump;
- подмена локального исполняемого файла SRI;
- инъекция команд через пути/имена;
- случайная публикация личных путей или секретов.

## Контроли

- только loopback; `--allow-remote` и non-loopback host отклоняются;
- Host allow-list и same-origin POST checks (`Origin`, `Sec-Fetch-Site`);
  POST без Origin отклоняется;
- path API: только `inputs/` и `artifacts/uploads/`;
- upload: 300 MB, 12 файлов, 160 MB на файл; `.nav/.txt/.gltf/.bin`;
- map names: `[A-Za-z0-9_-]{1,64}`;
- имена файлов сокращаются до basename;
- отклонённые upload directories удаляются; старые uploads/jobs очищаются;
- glTF sidecar не может выходить за каталог glTF;
- subprocess без `shell=True`;
- не более двух одновременных jobs; лишние получают `429`;
- timeout 900 s; на Windows завершается дерево процессов, включая SRI;
- SRI: explicit path или `CS2MB_SRI`, затем packaged locations;
- путь, версия и SHA-256 SRI записываются в manifest;
- preparation и analysis manifests используют `<CS2_GAME>`, `<INPUT>/...`,
  bundle-relative outputs и `<PYTHON>`, без личных абсолютных путей и username;
- скомпилированные ресурсы считаются недоверенным вводом; SRI сообщает
  контролируемые ошибки и тесселирует кривые примитивы с ограничением;
- viewer: `default-src 'none'`, `connect-src 'none'`,
  `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: no-referrer`,
  `Cross-Origin-Resource-Policy: same-origin`, `Cache-Control: no-store`;
- intake UI: CSP response header + meta policy, `X-Frame-Options: DENY`,
  `nosniff`, `Cross-Origin-Resource-Policy: same-origin`;
- `.gitignore` исключает игровые ресурсы, uploads, local config и build output;
- tracked tree проходит `tools/security_scan.py`.

## Аудит Git и release

- tracked tree не содержит личных Windows-путей, имён, ключей, токенов,
  `.env` или игровых ресурсов;
- `docs/assets/` содержит оригинальный логотип, оригинальные SVG-схемы и
  реальные скриншоты текущего приложения/сайта;
- `config/paths.local.json`, `tools/bin/*.exe` и `sri/dist/` игнорируются;
- оба workflow проверяют Python, сборку SRI, тесты и сайт;
- release содержит SRI, портативный Python runtime, checksums, SBOM и notices;
  binary не коммитится в Git;
- старые commit-объекты могут содержать исторические примеры путей; текущий
  `main` чистый, rewrite истории без разрешения не выполнялся.

## Аудит 3DsVW (2026-11-24)

3DsVW добавляет второй viewer сгенерированных данных и новые server routes.
Проверено:

- `/viewer3d/<map>/<job>/` и `/viewer3d/assets/`; map/job ID используют строгий
  regex, как и job API.
- Resolved paths остаются внутри фиксированного asset root или каталога
  `viewer3d/` задачи. Percent-encoded traversal, backslashes, NUL, отсутствующие
  файлы и произвольные суффиксы дают 404.
- Общая viewer-страница отдаётся из фиксированного asset root; каталог задачи не
  может её подменить.
- `viewer3d/build.py` нормализует glTF: заполняет `bufferViews[].buffer`,
  отклоняет внешние/отсутствующие sidecars и несовпадение длины buffer, удаляет
  images/textures/animations/skins и ограничивает glTF, sidecar, nodes/accessors
  и число collision-треугольников.
- CSP viewer: `default-src 'none'; script-src 'self'; connect-src 'self'`; без
  inline scripts и внешних origin.
- Метаданные объектов/NAV/entities выводятся через `textContent`/DOM nodes, без
  `innerHTML` для сгенерированных данных.
- `postMessage` настроек принимается только с того же origin.
- Endpoint-тесты покрывают traversal, неверные ID, отсутствующие bundles, CSP,
  content type и confined paths.
- Builder-тесты покрывают синтетические NAV/glTF, удаление текстур и отклонение
  внешнего buffer.

3DsVW остаётся локальным read-only viewer. Он не исполняет загруженный код и не
загружает внешние assets. Локальный процесс, способный переписать generated
files, находится вне этой модели угроз.

## Остаточные риски

- Python-парсеры не sandbox; не запускайте неизвестные файлы без необходимости.
- Upload bodies читаются в память до 300 MB.
- У сервера нет аутентификации; remote binding отключён, не выставляйте
  loopback-сервер через небезопасный proxy.
- SRI — доверенный локальный бинарник; hash не является подписью кода.
- SRI использует upstream MIT-библиотеку; будущее изменение библиотеки или
  формата CS2 может потребовать обновления.
- CSP intake UI передаётся заголовком и meta; `frame-ancestors` из meta не
  применяется, но заголовок и `X-Frame-Options: DENY` защищают framing.
- Авто-подготовка читает выбранную папку CS2; указывайте только доверенную
  установку игры.

## Проверка

```powershell
python -m unittest discover -s tests -v
python tools\security_scan.py
python -m compileall -q app tools movement simulation prototype
```

Полная английская версия: [SECURITY.md](SECURITY.md).
