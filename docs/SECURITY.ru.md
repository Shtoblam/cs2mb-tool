# SECURITY — pre-alpha v1.0

Приложение локальное и работает только с файлами пользователя.

**Область:** `app/server.py`, auto-generation pipeline, `source2/`,
`tools/source2.py`, пользовательские файлы.

## Управление обновлениями безопасности

Работы по безопасности ведутся в [SECURITY_BACKLOG.md](SECURITY_BACKLOG.md).
Первый baseline-апдейт добавляет CSP, referrer и cross-origin response headers
для intake UI и соответствующий regression test. Открытых critical/high
application-находок сейчас нет; оставшиеся работы по process, concurrency и
endpoint-тестам отслеживаются по приоритету.

## Что оно не делает

- не запускает CS2/Steam;
- не читает память игры;
- не взаимодействует с anti-cheat;
- не подключается к игровым серверам;
- не отправляет телеметрию/файлы наружу;
- не пишет в каталог игры.

## VAC / anti-cheat аудит

Дата: **2026-10-20**; последующее усиление viewer/UI проверено
**2026-11-20**, hardening response headers intake UI — **2026-11-23**,
внутренний Source 2 engine — **2026-11-23**. Проверены `app/server.py`,
`app/index.html`, `tools/prepare_map.py`, `tools/source2.py`, `source2/`,
`tools/auto_generate.py`, viewer и runtime-модули.

Результат: **взаимодействия с VAC не найдено**. Это статический обзор кода и
зависимостей, а не сертификация безопасности и не гарантия будущей политики
Valve.

- нет `cs2.exe`/`steam.exe`, перечисления процессов и attach;
- нет `OpenProcess`, `ReadProcessMemory`, `WriteProcessMemory`,
  `CreateRemoteThread`, `VirtualAllocEx`, DLL-инъекций и хуков;
- нет оверлея, автоматизации ввода, консольных команд и участия в матче;
- нет связи со Steam, игровыми серверами, VAC или внешним API;
- нет доступа к памяти игры и записи в каталог игры;
- не нужен администратор/root;
- дочерние процессы: локальный Python pipeline и собственный
  `cs2mb-source2`; Valve diagnostic tool и Source2Viewer-CLI не запускаются.

Приложение можно использовать при полностью закрытой CS2. Viewer —
self-contained HTML без внешнего JS/CSS/трекеров. HTTP-сервер по умолчанию
только loopback.

**Это не абсолютная гарантия:** Valve может изменить правила. Утверждение
относится к этому коду и перечисленным зависимостям, а не к любым сторонним
файлам, которые пользователь положит в `tools/bin/`.

**Зачем папка CS2:** только для необязательного режима Prepare + Generate.
Приложение read-only открывает map VPK, nav, entity lump и
`world_physics.vmdl_c`, а результаты пишет в `artifacts/`. Upload/drop не
требует доступа к папке игры.

**Внутренний Source 2 engine:** `cs2mb-source2` собирается из `source2/` в
этом репозитории и подключает MIT-библиотеку ValveResourceFormat 20.1.7467
непосредственно в процессе. Он разбирает binary KV3, Zstandard/LZ4, PHYS и
EntityLump, не скачивает обновления, не ходит в сеть и не подключается к CS2.
Это локальный доверенный бинарник: устанавливайте его со страницы релизов
CS2MB, сверяйте SHA-256 с `SHA256SUMS.txt` и держите вне каталога игры.
`prepare_map.py` записывает путь, версию и SHA-256 в `prepared_manifest.json`.
Устаревший `CS2MB_SOURCE2`/`--source2` приводит к ошибке, а не к молчаливому
выбору другого exe.

**Удалённые внешние runtime-инструменты:** Source2Viewer-CLI и
`resourceinfo.exe` больше не ищутся и не запускаются приложением. Инструкции
по их установке удалены из обычного setup. Upload-режим по-прежнему принимает
подготовленные `.gltf`/`.bin` и entity text.

## Контроли

- bind `127.0.0.1` по умолчанию; remote bind только `--allow-remote`;
- path API: только `inputs/` и `artifacts/uploads/`;
- POST origin guard;
- upload: 300 MB, 12 файлов, 160 MB на файл, только `.nav/.txt/.gltf/.bin`;
- glTF sidecar не может выходить за каталог glTF;
- subprocess без `shell=True`; timeout действует и для engine-вызовов;
- engine: явный путь или `CS2MB_SOURCE2`, затем упакованные locations;
  устаревший override не откатывается молча;
- путь, версия и SHA-256 engine записываются в preparation manifest;
- скомпилированные ресурсы считаются недоверенным вводом; engine сообщает
  контролируемые ошибки и тесселирует кривые примитивы с ограниченным числом
  колец;
- job timeout 900 s;
- сгенерированный viewer: ограничительный CSP в HTTP-заголовке
  (`default-src 'none'`, `connect-src 'none'`), `X-Frame-Options: SAMEORIGIN`,
  `Referrer-Policy: no-referrer`, `Cross-Origin-Resource-Policy: same-origin`
  и `Cache-Control: no-store`;
- intake UI: ограничительный CSP в HTTP-заголовке и соответствующая `<meta>`
  policy, а также `Referrer-Policy: no-referrer` и соответствующий referrer
  meta-элемент; ответ содержит `X-Content-Type-Options: nosniff`,
  `X-Frame-Options: DENY`, `Cross-Origin-Resource-Policy: same-origin` и
  `Cache-Control: no-store`;
- `.gitignore` исключает игровые ресурсы и uploads.

## Аудит Git

- текущее tracked-дерево: нет личных Windows-путей, имён, ключей, токенов,
  `.env` и игровых ресурсов;
- в `docs/assets/` только абстрактные SVG-баннеры/схемы и один скриншот UI;
  карт и игровых ассетов нет;
- `config/paths.local.json`, `tools/bin/*.exe` и `source2/dist/` игнорируются;
- в Git отслеживаются два GitHub Actions workflow: `tests.yml` запускает
  Python-проверки, сборку engine и engine-backed тесты; `pages.yml` собирает и
  публикует статический сайт по явному списку файлов. Deploy-секреты не
  отслеживаются;
- release assets содержат self-contained engine zip, checksums, license и
  notices; сам engine не коммитится в Git;
- в старых commit-объектах могут быть исторические примеры путей; текущий
  `main` чистый, rewrite истории без разрешения не выполнялся. Секретных
  ключей в аудите истории не найдено.

## Остаточные риски

Python-парсеры не sandbox. Не запускайте неизвестные файлы без необходимости.
Сервер не имеет аутентификации — не выставляйте его в интернет. CSP intake UI
теперь передаётся и HTTP-заголовком, и meta-элементом. `frame-ancestors`
не применяется из meta, но заголовок и `X-Frame-Options: DENY` обеспечивают
защиту framing. Старые commit-объекты Git могут содержать исторические пути;
очистка истории — только с отдельным согласованием.

Engine — локальный доверенный бинарник. Хеш выявляет повреждение/подмену, но
не является подписью кода; скачивайте его только со страницы релизов CS2MB.
Engine использует upstream MIT-библиотеку; будущее изменение библиотеки или
формата CS2 может потребовать обновления, а текущая валидация привязана к
записанной сборке игры.

Авто-подготовка читает выбранную папку CS2. Указывайте только доверенную
установку игры; не направляйте её на каталог, который контролирует посторонний.

## Проверка

```powershell
python -m unittest discover -s tests -v
python tools\security_scan.py
```

Полная английская версия: [SECURITY.md](SECURITY.md).
