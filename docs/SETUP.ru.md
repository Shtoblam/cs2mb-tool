# Установка и troubleshooting

Это руководство устанавливает локальное приложение CS2 Map Balance в Windows
и объясняет, как собрать карту из установленной CS2 или из загруженных файлов.

Приложение — локальный анализатор файлов. Оно не запускает CS2/Steam, не читает
память игры и не взаимодействует с anti-cheat. Локальный сервер должен
оставаться на `127.0.0.1`.

## 1. Что нужно

- Windows 10/11 **x64**.
- **Python 3.13 x64** — тестируемая версия. Шаг `pip install` не нужен.
- Папка проекта или source ZIP из ветки `main`.
- Установленная CS2 — если нужен режим **Prepare + Generate from installed CS2**.
- **Source2Viewer-CLI 20.1** — для автоматического экспорта physics collision.
  Не нужен, если у вас уже есть physics glTF + `.bin`.

Права администратора, установка в систему и изменение файлов игры не нужны.

## 2. Установить Python 3.13

1. Откройте <https://www.python.org/downloads/windows/>.
2. Скачайте **Windows installer (64-bit)** для Python 3.13.
3. Включите **Add python.exe to PATH** и нажмите **Install Now**.
4. Откройте **новое** окно PowerShell и проверьте:

```powershell
py -3.13 --version
python --version
```

Если `python` открывает Microsoft Store или не найден, используйте `py -3.13`
во всех командах ниже либо переустановите Python с PATH.

## 3. Получить проект

Репозиторий публичный.

Вариант A — source ZIP:

1. Скачайте <https://github.com/Shtoblam/cs2mb-tool/archive/refs/heads/main.zip>.
2. Распакуйте в обычную пользовательскую папку, например
   `%USERPROFILE%\Documents\cs2mapbalance`.

Вариант B — Git clone:

```powershell
git clone https://github.com/Shtoblam/cs2mb-tool.git
cd cs2mapbalance
```

**Не** распаковывайте проект внутрь папки CS2/Steam.

Проверьте, что в корне проекта есть `app`, `tools`, `docs`, `config` и
`README.md`:

```powershell
Get-ChildItem
```

## 4. Запустить локальное приложение

Из корня проекта:

```powershell
py -3.13 app\server.py --port 8765
```

Или, если `python` указывает на Python 3.13:

```powershell
python app\server.py --port 8765
```

Откройте <http://127.0.0.1:8765/>. Первый запуск откроет tutorial; кнопка
**? Установка** откроет его снова. `Ctrl+C` в PowerShell останавливает сервер.

Если порт 8765 занят:

```powershell
py -3.13 app\server.py --port 8766
```

Затем откройте `http://127.0.0.1:8766/`. Не выставляйте сервер в интернет.

## 5. Собрать карту

### Автоматический режим (рекомендуется)

1. Запустите приложение при закрытой CS2.
2. Укажите **CS2 game folder** — корень установки CS2.
3. Укажите **Map name**, например `de_mirage` или `de_dust2`.
4. Нажмите **Prepare + Generate**.
5. Дождитесь ссылки `viewer` и новой строки в `Map library`.

В выбранной папке должны быть:

```text
game\csgo\maps\<map>.vpk
game\csgo\gameinfo.gi
game\bin\win64\resourceinfo.exe
```

Найти её можно в Steam: **Библиотека → Counter-Strike 2 → Управление →
Просмотреть локальные файлы**. Приложение отклонит папку без структуры CS2.

### Режим файлов (без доступа к папке CS2)

1. Получите четыре файла по [инструкции](GETTING_FILES.ru.md).
2. Укажите **Map name**.
3. Перетащите `.nav`, entity `.txt`, `.gltf` и `.bin` в drop zone.
4. Нажмите **Generate map**.

`Skip clearance` занимает около 20 секунд на Dust2; полный clearance job —
около 2.5 минут на записанной тестовой машине. Viewer и строка library
появятся после завершения.

## 6. Source2Viewer-CLI

Source2Viewer-CLI — отдельный **MIT-инструмент** проекта
[ValveResourceFormat](https://github.com/ValveResourceFormat/ValveResourceFormat).
Он не входит в репозиторий, не скачивается автоматически и не нужен для
upload-режима.

Он конвертирует уже извлечённый `world_physics.vmdl_c` в:

```text
world_physics_physics.gltf
world_physics_physics.bin
```

Именно эти файлы читает анализатор. Source2Viewer не загружается в CS2, не
является anti-cheat и не работает с процессом игры.

### Скачать

Официальная страница релиза:

<https://github.com/ValveResourceFormat/ValveResourceFormat/releases/tag/20.1>

Для Windows x64 скачайте:

```text
cli-windows-x64.zip
```

Прямая ссылка:
<https://github.com/ValveResourceFormat/ValveResourceFormat/releases/download/20.1/cli-windows-x64.zip>

Не скачивайте `Source2Viewer.exe` для авто-режима — это GUI. Не используйте
Linux/macOS assets на Windows. В архиве:

```text
Source2Viewer-CLI.exe
libSkiaSharp.dll
spirv-cross.dll
```

Проверенные артефакты 20.1 (записано 2026-10-20):

```text
cli-windows-x64.zip
SHA-256 67AAF8A67A85CA60FD09FF343E62103A4CDF3A2D177FC656231D7D734C5B3AA3

Source2Viewer-CLI.exe (после распаковки)
SHA-256 EF9F6FB3943C30B73F0991BCE6654128727B0807968F7997A6BB014EFBEC8830
```

Это хэши проверенных артефактов, а не гарантия для будущих релизов. Сверяйте
источник и hash; **не отключайте Windows Defender** ради неизвестного exe.

### Куда положить для авто-режима

Распакуйте **все три файла** в `tools\bin` проекта:

```text
cs2mapbalance\
  app\
  config\
  docs\
  tools\
    bin\
      Source2Viewer-CLI.exe
      libSkiaSharp.dll
      spirv-cross.dll
```

Точный путь к executable:

```text
<PROJECT>\tools\bin\Source2Viewer-CLI.exe
```

Не кладите файлы:

- в `game\bin\win64` — не меняйте установку CS2;
- в папку Steam;
- в `C:\Windows`;
- в недоверенный каталог.

Exe и DLL игнорируются Git и не должны коммититься.

### Альтернатива: CLI вне проекта

Порядок поиска:

- при ручном запуске `tools/prepare_map.py`: `--s2v-cli`, затем переменная
  окружения `S2V_CLI`, затем `tools\bin\Source2Viewer-CLI.exe`;
- в локальном приложении: `S2V_CLI` либо `s2v_cli` из
  `config\paths.local.json`, затем `tools\bin\Source2Viewer-CLI.exe`. Сервер
  передаёт найденный путь в `prepare_map.py` как `--s2v-cli`.

Если держите CLI отдельно, все три файла должны лежать вместе:

```powershell
$env:S2V_CLI = "C:\Tools\Source2Viewer\Source2Viewer-CLI.exe"
py -3.13 app\server.py --port 8765
```

Или скопируйте шаблон и отредактируйте локальный конфиг:

```powershell
Copy-Item config\paths.example.json config\paths.local.json
notepad config\paths.local.json
```

Пример JSON (двойные обратные слеши обязательны):

```json
{
  "cs2_game": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Counter-Strike Global Offensive",
  "s2v_cli": "C:\\Tools\\Source2Viewer\\Source2Viewer-CLI.exe"
}
```

`config/paths.local.json` игнорируется Git. Это только локальное удобство.

### Проверка

```powershell
& ".\tools\bin\Source2Viewer-CLI.exe" --help
Get-FileHash ".\tools\bin\Source2Viewer-CLI.exe" -Algorithm SHA256
```

Перезапустите приложение и откройте <http://127.0.0.1:8765/>. В панели intake
должно появиться **S2V ready**. Если **S2V not configured**:

- exe называется точно `Source2Viewer-CLI.exe`;
- все три файла лежат в одной папке;
- приложение запущено из корня проекта;
- сервер перезапущен после изменения env/config.

### Если CLI не нужен

Загрузите готовый glTF + `.bin` или используйте Source2Viewer GUI
(`Source2Viewer.exe`), экспортировав `world_physics.vmdl_c` как
**glTF Separate**. Upload-режиму нужны только четыре файла карты.

## 7. Troubleshooting

| Проблема | Решение |
|---|---|
| `python` не найден / открывает Store | Используйте `py -3.13`; переустановите Python 3.13 с **Add python.exe to PATH**. |
| `ModuleNotFoundError` при запуске | Запускайте из корня проекта, не из `app\`; `pip install` не нужен. |
| `S2V not configured` | Положите все три файла CLI в `tools\bin` или задайте `S2V_CLI` / `config\paths.local.json`; перезапустите приложение. |
| Нет `libSkiaSharp.dll` | Распакуйте весь `cli-windows-x64.zip`, а не только exe. |
| `invalid CS2 game folder` | Выберите корень установки CS2 с `game\csgo\maps`, а не саму папку `maps`. |
| Map VPK не найден | Установите карту или используйте upload для workshop/нестандартных карт. |
| Порт занят | Запустите с `--port 8766` и откройте новый URL. |
| VPK заблокирован | Закройте CS2 на время авто-извлечения. |
| В viewer нет collision | Загрузите `.gltf` **и** `.bin`; sidecar обязателен. |
| Пустые route cards | Нужны стандартные callouts `BombsiteA`, `BombsiteB`, `Middle`; nav/collision при этом могут отрисоваться. |
| Windows Defender предупреждает о CLI | Не отключайте Defender; проверьте официальный источник и SHA-256 либо используйте upload. |

## 8. Остановить и удалить

Нажмите `Ctrl+C` в PowerShell. Программа не ставит службу, драйвер, запись в
реестр или что-либо в CS2. Удалите папку проекта; `tools\bin` удалите отдельно,
если CLI больше не нужен.

## 9. Связанная документация

- [Получение файлов](GETTING_FILES.ru.md) — ручные команды и форматы файлов.
- [Безопасность](SECURITY.ru.md) — модель угроз и контроли.
- [Индекс документации](README.md) — все документы проекта.
- [Setup in English](SETUP.md).
