# Установка и устранение неполадок

Это руководство устанавливает CS2 Map Balance `v1.1.1` на Windows и
объясняет, как получить карту из установленной CS2 или из загруженных файлов.

Приложение — локальный анализатор файлов только для чтения. Оно не запускает
CS2 или Steam, не читает память игры и не взаимодействует с античитом. Сервер
слушает `127.0.0.1`; remote binding отключён.

## 1. Требования

- Windows 10/11 **x64**.
- Полный пакет CS2MB `CS2MB-v1.1.1-win-x64.zip`.
- Браузер с WebGL2 для 3DsVW (актуальные Chrome, Edge или Firefox).
- Установленная CS2 для режима **Prepare + Generate from installed CS2**.
- Отдельная установка Python, `pip install`, .NET runtime, Source2Viewer-CLI и
  `resourceinfo.exe` для packaged build не нужны.

В пакет входят портативный Python 3.13 runtime и **SRI — Source Resource
Inspector** в `tools/bin/sri/cs2mb-sri.exe`.

## 2. Установка и запуск

1. Скачайте полный пакет со
   <https://github.com/Shtoblam/cs2mb-tool/releases/tag/v1.1.1>.
2. Сверьте архив с `SHA256SUMS.txt`.
3. Распакуйте в обычную пользовательскую папку, например
   `%USERPROFILE%\Documents\CS2MB`.
4. Запустите `Start-CS2MB.bat` (или `Start-CS2MB.ps1`).
5. Откройте <http://127.0.0.1:8765/>, если браузер не открылся автоматически.

Не распаковывайте пакет внутрь папки CS2/Steam.

Launcher использует `runtime\python.exe` из пакета, проверяет наличие SRI,
запускает локальный сервер и открывает URL. Права администратора и изменения
реестра не нужны.

## 3. Source checkout (для разработки)

Обычным пользователям нужен полный пакет. Для source checkout:

```powershell
git clone https://github.com/Shtoblam/cs2mb-tool.git
cd cs2mb-tool
py -3.13 tools\sri.py --status
py -3.13 app\server.py --port 8765
```

Требования source checkout:

- Python 3.13 x64;
- SRI в `tools/bin/sri/cs2mb-sri.exe` или `CS2MB_SRI`, указывающий на executable.

Сборка SRI из исходников:

```powershell
sri\build.ps1
```

Для сборки нужен .NET SDK 10.0.x; для обычного запуска — нет.

### Dry run

`python tools\prepare_map.py ... --dry-run` проверяет карту, пути игры и SRI,
печатает план извлечения/конвертации и не создаёт каталог или файлы результатов.
VPK не открывается, конвертация SRI не запускается, `auto_generate.py` не
запускается. Dry run для установленной CS2 в приложении работает так же;
upload/path режим по-прежнему пишет только pending manifest.

## 4. SRI — Source Resource Inspector

SRI — собственный компонент CS2MB для чтения скомпилированных ресурсов Source 2.
Это не универсальный просмотрщик/редактор Source 2 и не переименованный сторонний
CLI.

- `world_physics.vmdl_c` → PHYS → glTF + `.bin`;
- `default_ents.vents_c` → EntityLump → entity text;
- координаты остаются в Hammer units и Source axes (`x`, `y`, `z-up`);
- `InteractAs`, `SurfaceProperty` и `CollisionGroup` сохраняются;
- sphere/capsule примитивы тесселируются с ограниченным числом колец;
- существующий collision loader и модули анализа не изменены.

Проверка компонента:

```powershell
& ".\tools\bin\sri\cs2mb-sri.exe" --version
py -3.13 tools\sri.py --status
Get-FileHash ".\tools\bin\sri\cs2mb-sri.exe" -Algorithm SHA256
```

Ожидается `cs2mb-sri 1.0.0 (SRI — Source Resource Inspector)` и
`"ready": true`. В приложении отображается **SRI ready** с версией.

Места поиска по приоритету:

- переменная `CS2MB_SRI`;
- `tools\bin\sri\cs2mb-sri.exe`;
- `tools\bin\cs2mb-sri.exe`;
- `sri\bin\win-x64\cs2mb-sri.exe`;
- `--sri <path>` для ручного `tools/prepare_map.py`.

Явный путь или `CS2MB_SRI` имеют приоритет: устаревшее значение приводит к
ошибке, а не к молчаливому выбору другого файла.

## 4.1 3DsVW — 3D Source Map Viewer

3DsVW входит в пакет в `viewer3d/`; three.js runtime упакован в
`viewer3d/assets/vendor/`. Нужен WebGL2, сеть не требуется.

После завершения задачи откройте **Viewer**:

- 3DsVW встроен в приложение;
- можно открыть отдельную вкладку;
- можно переключиться на существующий 2D viewer;
- слои collision, floor, wall, clip, NAV, entity, site label и route
  переключаются независимо;
- камера: Fit, Top, Iso, Reset;
- клик по геометрии, NAV или entity показывает доступные метаданные.

Viewer показывает SRI PHYS collision-геометрию, а не render-world, материалы или
текстуры. Управление и ограничения — в [USER_GUIDE.ru.md](USER_GUIDE.ru.md).

## 5. Генерация карты

### Автоматический режим (рекомендуется)

1. Запустите приложение при закрытой CS2.
2. Укажите **CS2 game folder** — корень установки CS2.
3. Укажите **Map name**, например `de_mirage` или `de_dust2`.
4. Нажмите **Prepare + Generate**.
5. Дождитесь ссылки на viewer и новой строки в Map library.

В папке должны быть:

```text
game\csgo\maps\<map>.vpk
game\csgo\gameinfo.gi
```

Найти её: Steam → **Библиотека → Counter-Strike 2 → Управление → Просмотреть
локальные файлы**. Игра используется только для чтения; результаты пишутся в
`artifacts/`.

### Режим файлов (без доступа к папке CS2)

1. Подготовьте четыре файла по
   [GETTING_FILES.ru.md](GETTING_FILES.ru.md).
2. Укажите **Map name**.
3. Перетащите `.nav`, entity `.txt`, `.gltf` и `.bin` в drop zone.
4. Нажмите **Generate map**.

`Skip clearance` занимает около 20 секунд на Dust2; полная проверка — около
2.5 минут на тестовой машине.

## 6. Security controls

- loopback-only сервер; `--allow-remote` отклоняется;
- Host и Origin checks для локального HTTP surface;
- upload limits: 300 MB, 12 файлов, 160 MB на файл;
- разрешены `.nav`, `.txt`, `.gltf`, `.bin`;
- path mode ограничен `inputs/` и `artifacts/uploads/`;
- не более двух одновременных jobs;
- timeout 900 s с завершением дерева процессов Windows;
- старые job records и upload directories очищаются;
- нет телеметрии, внешних загрузок, доступа к процессу игры и anti-cheat;
- SRI — локальный доверенный бинарник; сверяйте SHA-256.

Preparation manifest хранит provenance без личных абсолютных путей: вместо
имени пользователя и home directory используются `<CS2_GAME>` и `prepared/...`.

## 7. Устранение неполадок

| Симптом | Действие |
|---|---|
| `SRI not installed` | Проверьте `tools\bin\sri\cs2mb-sri.exe`; запускайте `Start-CS2MB.ps1` из корня пакета. |
| `SRI failed` | Проверьте `artifacts/.../prepared/sri.log`; убедитесь, что ресурс относится к поддерживаемой сборке CS2. |
| Launcher не находит Python | Используйте полный пакет или установите Python 3.13 x64 для source checkout. |
| `invalid CS2 folder` | Выберите корень CS2 с `game\csgo\maps`, а не папку `maps`. |
| Порт занят | Запустите с `--port 8766`. |
| `no .bin` | Загружайте `.gltf` и `.bin` вместе. |
| `too many active jobs` | Дождитесь завершения job; лимит — два. |
| `missing Origin header` | Используйте локальный web UI; прямые non-browser POST отклоняются. |

## 8. Ограничения

- SRI работает только на Windows x64.
- Кривые collision-примитивы тесселируются приближённо.
- Поддержка entity/PHYS проверена на записанной сборке CS2; будущее изменение
  формата Valve может потребовать обновления SRI.
- Movement-модель остаётся straight-line и не включает combat, utility,
  visibility или решения игроков.
- Полный clearance проверялся на Dust2 и Nuke; остальные карты использовали
  `Skip clearance`.

См. [SECURITY.ru.md](SECURITY.ru.md), [VALIDATION.md](VALIDATION.md) и
[STATE.md](STATE.md).
