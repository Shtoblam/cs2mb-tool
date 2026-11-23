# Получение файлов карты

Нужны четыре файла:

```text
<map>.nav
entities.txt
world_physics_physics.gltf
world_physics_physics.bin
```

Приложение не запускает CS2/Steam и не пишет в каталог игры. Все команды
ниже только читают игру.

## Быстрый путь: авто-извлечение

Если не хочется запускать команды вручную:

1. Положить `Source2Viewer-CLI.exe` в `tools/bin/` или задать `S2V_CLI`.
2. Запустить приложение.
3. Указать `CS2 game folder` и map name.
4. Нажать **Prepare + Generate**.

Приложение выполнит те же шаги внутри. Ручной путь ниже — fallback и для
диагностики.

## Source2Viewer-CLI

Для авто-генерации скачайте официальный Windows x64 CLI-архив со
[страницы ValveResourceFormat 20.1](https://github.com/ValveResourceFormat/ValveResourceFormat/releases/tag/20.1):

```text
cli-windows-x64.zip
```

Распакуйте **все три файла** в папку проекта:

```text
cs2mapbalance\tools\bin\Source2Viewer-CLI.exe
cs2mapbalance\tools\bin\libSkiaSharp.dll
cs2mapbalance\tools\bin\spirv-cross.dll
```

Не кладите их в папку игры или Steam. Git их игнорирует. Альтернатива — держать
их вместе в другом месте и задать `S2V_CLI` на полный путь к exe либо прописать
`s2v_cli` в `config\paths.local.json`.

Проверка:

```powershell
& ".\tools\bin\Source2Viewer-CLI.exe" --help
Get-FileHash ".\tools\bin\Source2Viewer-CLI.exe" -Algorithm SHA256
```

После перезапуска приложения в intake должно быть `S2V ready`. Полный гайд:
**[SETUP.ru.md](SETUP.ru.md)**.

## 1. Переменные

```powershell
$CS2  = "<CS2_GAME>"
$TEMP = "<TEMP>\cs2mb"
$MAP  = "de_mirage"
New-Item -ItemType Directory -Force $TEMP | Out-Null
```

## 2. Nav

```powershell
python tools\vpk_read.py "$CS2\game\csgo\maps\$MAP.vpk" `
  extract "maps/$MAP.nav" "$TEMP\$MAP.nav"
```

## 3. Entity и physics

```powershell
python tools\vpk_read.py "$CS2\game\csgo\maps\$MAP.vpk" `
  extract "maps/$MAP/entities/default_ents.vents_c" "$TEMP\default_ents.vents_c"
python tools\vpk_read.py "$CS2\game\csgo\maps\$MAP.vpk" `
  extract "maps/$MAP/world_physics.vmdl_c" "$TEMP\world_physics.vmdl_c"
```

## 4. Entity dump

```powershell
& "$CS2\game\bin\win64\resourceinfo.exe" `
  -game "$CS2\game\csgo" `
  -i "$TEMP\default_ents.vents_c" -all `
  > "$TEMP\entities.txt"
```

PowerShell может записать файл в UTF-16. Приложение принимает UTF-8,
UTF-8 BOM и UTF-16 LE/BE.

## 5. Physics glTF

```powershell
& "<S2V>\Source2Viewer-CLI.exe" `
  -i "$TEMP\world_physics.vmdl_c" `
  -o "$TEMP\world_physics.gltf" `
  -d --gltf_export_format gltf `
  --gltf_export_materials `
  --game "$CS2\game\csgo\gameinfo.gi"
```

Появятся:

```text
<TEMP>\world_physics_physics.gltf
<TEMP>\world_physics_physics.bin
```

`.bin` обязателен. Source2Viewer-CLI можно положить в `tools/bin/` или
указать через `S2V_CLI`.

## 6. Загрузка

```powershell
python app\server.py --port 8765
```

Открыть <http://127.0.0.1:8765/>:

- либо указать `CS2 game folder` и нажать **Prepare + Generate** —
  программа сама извлечёт nav/entities/collision;
- либо перетащить четыре файла в drop zone.

## 7. Проблемы

- **Нет `.bin`** — загрузить/экспортировать `.bin` вместе с `.gltf`.
- **Пустые route cards** — нужны стандартные callouts `BombsiteA`,
  `BombsiteB`, `Middle`.
- **Нет `world_physics.vmdl_c`** — нестандартная карта; приложение сообщит
  об отсутствии входа.
- **Большие файлы** — используйте `inputs/<map>/` или upload по лимитам
  сервера.

## 8. Безопасность

- приложение не запускает игру и не читает память;
- не коммитить игровые ресурсы;
- не выставлять локальный сервер в интернет.
