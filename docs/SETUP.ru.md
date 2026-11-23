# Установка и устранение неполадок

Это руководство устанавливает локальное приложение CS2 Map Balance на Windows
и объясняет, как получить карту из установленной CS2 или из загруженных файлов.

Приложение — локальный анализатор файлов только для чтения. Оно не запускает
CS2 или Steam, не читает память игры и не взаимодействует с античитом. Сервер
должен оставаться на `127.0.0.1`.

## 1. Требования

- Windows 10/11 **x64**.
- **Python 3.13 x64** — проверенная версия. Шаг `pip install` не нужен.
- Папка проекта или ZIP исходников из `main`.
- Установленная CS2 для режима **Prepare + Generate from installed CS2**.
- Компонент **cs2mb-source2** для автоматического разбора PHYS и EntityLump.
  Это собственный self-contained компонент CS2MB. .NET runtime,
  Source2Viewer-CLI и `resourceinfo.exe` не требуются.

Права администратора, общесистемная установка и изменение файлов игры не
нужны.

## 2. Установка Python 3.13

1. Откройте <https://www.python.org/downloads/windows/>.
2. Скачайте **Windows installer (64-bit)** для Python 3.13.
3. Включите **Add python.exe to PATH** и выберите **Install Now**.
4. Откройте **новое** окно PowerShell и проверьте:

```powershell
py -3.13 --version
python --version
```

Если `python` открывает Microsoft Store или не найден, используйте `py -3.13`
во всех командах ниже либо переустановите Python с включённым PATH.

## 3. Получение проекта

Репозиторий публичный: <https://github.com/Shtoblam/cs2mb-tool>.

Вариант A — ZIP исходников:

1. Скачайте <https://github.com/Shtoblam/cs2mb-tool/archive/refs/heads/main.zip>.
2. Распакуйте в обычную пользовательскую папку, например
   `%USERPROFILE%\Documents\cs2mb-tool`.

Вариант B — Git:

```powershell
git clone https://github.com/Shtoblam/cs2mb-tool.git
cd cs2mb-tool
```

Не распаковывайте проект внутрь папки CS2/Steam.

## 4. Установка внутреннего Source 2 engine

Автоматический режим использует `cs2mb-source2.exe`, собранный из `source2/`
в этом репозитории. Он подключает MIT-библиотеку ValveResourceFormat
непосредственно в процессе и не запускает сторонний CLI.

1. Откройте страницу релизов CS2MB:
   <https://github.com/Shtoblam/cs2mb-tool/releases/latest>.
2. Скачайте `cs2mb-source2-win-x64.zip`.
3. Сверьте архив с `SHA256SUMS.txt` из того же релиза.
4. Распакуйте `cs2mb-source2.exe` в:

```text
<PROJECT>\tools\bin\source2\cs2mb-source2.exe
```

5. Проверьте установку из корня проекта:

```powershell
& ".\tools\bin\source2\cs2mb-source2.exe" --version
py -3.13 tools\source2.py --status
Get-FileHash ".\tools\bin\source2\cs2mb-source2.exe" -Algorithm SHA256
```

Ожидаемый статус: `"ready": true` и версия `cs2mb-source2 1.0.0`. Исполняемый
файл игнорируется Git. Не кладите его в установку CS2/Steam, `C:\Windows` или
недоверенный путь.

Компонент self-contained. .NET runtime, Source2Viewer-CLI, `resourceinfo.exe`
и настройка `S2V_CLI` не используются. Дополнительные места поиска:

- переменная окружения `CS2MB_SOURCE2`;
- `tools\bin\cs2mb-source2.exe`;
- `source2\bin\win-x64\cs2mb-source2.exe`;
- `--source2 <path>` для ручного запуска `tools/prepare_map.py`.

Явный путь или `CS2MB_SOURCE2` имеют приоритет: устаревшее значение приводит
к ошибке, а не к молчаливому запуску другого файла.

### Сборка engine из исходников (необязательно)

Обычным пользователям этот шаг не нужен. Для сборки требуется .NET SDK 10.0.x;
опубликованный exe не требует SDK или runtime.

```powershell
source2\build.ps1
source2\build.ps1 -Install   # копирует в tools\bin\source2\
```

Версии закреплены в `source2/global.json`, `source2/Cs2mb.Source2/Cs2mb.Source2.csproj`
и `packages.lock.json`. См. `source2/README.md` и
`source2/THIRD_PARTY_NOTICES.md`.

## 5. Запуск приложения

Из корня проекта:

```powershell
py -3.13 app\server.py --port 8765
```

Откройте <http://127.0.0.1:8765/>. При первом запуске открывается обучение;
кнопка обучения открывает его снова. Остановка — `Ctrl+C` в PowerShell.

Если порт 8765 занят:

```powershell
py -3.13 app\server.py --port 8766
```

Затем откройте `http://127.0.0.1:8766/`. Не выставляйте сервер в интернет.

## 6. Генерация карты

### Автоматический режим (рекомендуется)

1. Запустите приложение при закрытой CS2.
2. Укажите **CS2 game folder** — корень установки CS2.
3. Укажите **Map name**, например `de_mirage` или `de_dust2`.
4. Нажмите **Prepare + Generate**.
5. Дождитесь ссылки на viewer и новой строки в Map library.

В выбранной папке должны быть:

```text
game\csgo\maps\<map>.vpk
game\csgo\gameinfo.gi
```

Найти её: Steam → **Библиотека → Counter-Strike 2 → Управление → Просмотреть
локальные файлы**. Папка игры используется только для чтения; извлечённые
ресурсы и результаты пишутся в `artifacts/`.

Индикатор показывает `engine ready` и версию компонента. `engine not
installed` означает, что exe отсутствует или путь неверен.

### Режим файлов (без доступа к папке CS2)

1. Подготовьте четыре файла по
   [GETTING_FILES.ru.md](GETTING_FILES.ru.md).
2. Укажите **Map name**.
3. Перетащите `.nav`, entity `.txt`, `.gltf` и `.bin` в drop zone.
4. Нажмите **Generate map**.

`Skip clearance` занимает около 20 секунд на Dust2; полная проверка — около
2.5 минут на тестовой машине. Viewer и строка library появляются после job.

## 7. Что делает внутренний engine

```text
map VPK (read-only)
   ├─ <map>.nav                  → существующий Python NAV parser
   ├─ default_ents.vents_c       → cs2mb-source2 entities → entity dump
   └─ world_physics.vmdl_c       → cs2mb-source2 phys     → glTF + .bin
```

- `cs2mb-source2 entities` разбирает скомпилированный EntityLump и пишет
  построчный dump для существующего parser. Сохраняются classname, origin,
  angles, targetname, callouts и остальные свойства.
- `cs2mb-source2 phys` разбирает PHYS, выдаёт collision-треугольники с
  группировкой по collision attribute и surface property и сохраняет
  `InteractAs`. Координаты остаются в Hammer units и Source axes (`x`, `y`,
  `z-up`); устаревшая glTF node matrix не применяется.
- Существующие collision loader, movement model, routing и balance logic не
  изменены.

Конвертер не подменяет physics geometry рендер-геометрией: читается именно
`world_physics.vmdl_c`.

## 8. Устранение неполадок

| Симптом | Действие |
|---|---|
| `python not found` | Используйте `py -3.13`; переустановите Python с PATH. |
| `engine not installed` | Распакуйте `cs2mb-source2.exe` в `tools\bin\source2\`; перезапустите сервер. |
| `cs2mb-source2 failed` | Проверьте `artifacts/.../prepared/source2.log`; убедитесь, что файл относится к поддерживаемой сборке CS2. |
| Large collision output | Карты с большим числом треугольников (например Inferno) дают крупный `.bin` и обрабатываются дольше; это ожидаемо. |
| `invalid CS2 folder` | Выберите корень CS2 с `game\csgo\maps`, а не папку `maps`. |
| Порт занят | Запустите с `--port 8766` и откройте новый URL. |
| `no .bin` | Загружайте/экспортируйте `.gltf` и `.bin` вместе. |

## 9. Безопасность и ограничения

- Сервер по умолчанию только loopback; не выставляйте его в LAN или интернет.
- Ограничения upload, allow-list путей, проверка Origin, таймауты job и
  security-заголовки сохранены.
- Нет телеметрии, внешних загрузок, доступа к процессу игры, инъекций и
  взаимодействия с античитом.
- Engine — локальный доверенный компонент. Сверяйте SHA-256 с релизом. Он
  обрабатывает недоверенные бинарные ресурсы и сообщает контролируемые ошибки.
- Текущий конвертер выдаёт mesh и convex hull collision напрямую, а
  sphere/capsule примитивы тесселирует с ограниченным числом колец. Кривые
  поверхности — приближение для анализа, а не точная аналитическая collision.
- Поддержка entity и physics проверена на установленной сборке CS2 из
  [STATE.md](STATE.md); будущее изменение формата Valve может потребовать
  обновления engine.

Engine реализован независимо для CS2MB. ValveResourceFormat — MIT-библиотека
сообщества, а не продукт Valve и не официальный CS2 SDK.
