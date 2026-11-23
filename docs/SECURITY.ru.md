# SECURITY — pre-alpha v1.0

Приложение локальное и работает только с файлами пользователя.

## Что оно не делает

- не запускает CS2/Steam;
- не читает память игры;
- не взаимодействует с anti-cheat;
- не подключается к игровым серверам;
- не отправляет телеметрию/файлы наружу;
- не пишет в каталог игры.

## VAC / anti-cheat аудит

Дата: **2026-10-20**; последующее усиление viewer/UI проверено
**2026-11-20**, а hardening response headers intake UI — **2026-11-23**. Проверены `app/server.py`, `app/index.html`,
`tools/prepare_map.py`, `tools/auto_generate.py`, viewer и runtime-модули.

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
- дочерние процессы: локальный Python pipeline, read-only
  `resourceinfo.exe` Valve и опциональный MIT Source2Viewer-CLI.

Приложение можно использовать при полностью закрытой CS2. Viewer —
self-contained HTML без внешнего JS/CSS/трекеров. HTTP-сервер по умолчанию
только loopback.

**Это не абсолютная гарантия:** Valve может изменить правила. Утверждение
относится к этому коду и перечисленным зависимостям, а не к любым сторонним
файлам, которые пользователь положит в `tools/bin/`.

**Зачем папка CS2:** только для необязательного режима Prepare + Generate.
Приложение read-only открывает map VPK, nav, entity lump и
`world_physics.vmdl_c`, а результаты пишет в `artifacts/`. Upload/drop не
требует доступа к папке игры. `resourceinfo.exe` — диагностика Valve;
Source2Viewer-CLI только конвертирует извлечённый vmdl в glTF и не
подключается к игре.

## Контроли

- bind `127.0.0.1` по умолчанию; remote bind только `--allow-remote`;
- path API: только `inputs/` и `artifacts/uploads/`;
- POST origin guard;
- upload: 300 MB, 12 файлов, 160 MB на файл, только `.nav/.txt/.gltf/.bin`;
- glTF sidecar не может выходить за каталог glTF;
- subprocess без `shell=True`;
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
- `config/paths.local.json` и `tools/bin/*.exe` игнорируются;
- в Git отслеживаются два GitHub Actions workflow: `tests.yml` запускает
  компиляцию, unit-тесты и hygiene scan; `pages.yml` собирает и публикует
  статический сайт по явному списку файлов. Deploy-секреты не отслеживаются;
- release assets содержат только исходники/документацию;
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

Авто-подготовка запускает `resourceinfo.exe` из выбранной папки CS2. Указывайте
только доверенную установку игры; не направляйте её на каталог, который
контролирует посторонний.

## Проверка

```powershell
python -m unittest discover -s tests -v
python tools\security_scan.py
```

Полная английская версия: [SECURITY.md](SECURITY.md).
