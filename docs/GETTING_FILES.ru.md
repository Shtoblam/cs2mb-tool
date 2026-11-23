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

1. Установить `cs2mb-source2.exe` в `tools/bin/source2/` или задать `CS2MB_SOURCE2`.
2. Запустить приложение.
3. Указать `CS2 game folder` и map name.
4. Нажать **Prepare + Generate**.

Приложение выполнит те же шаги внутри. Ручной путь ниже — fallback и для
диагностики.

## Внутренний Source 2 engine

Скачайте `cs2mb-source2-win-x64.zip` со
[страницы релизов CS2MB](https://github.com/Shtoblam/cs2mb-tool/releases/tag/source2-v1.0.0)
и распакуйте self-contained exe:

```text
cs2mb-tool\tools\bin\source2\cs2mb-source2.exe
```

.NET runtime, Source2Viewer-CLI и `resourceinfo.exe` не нужны. Проверка:

```powershell
& ".\tools\bin\source2\cs2mb-source2.exe" --version
Get-FileHash ".\tools\bin\source2\cs2mb-source2.exe" -Algorithm SHA256
```

После перезапуска приложения в intake должно быть `engine ready`. Полный гайд:
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
& ".\tools\bin\source2\cs2mb-source2.exe" entities `
  --input "$TEMP\default_ents.vents_c" `
  --output "$TEMP\entities.txt"
```

Файл пишется в UTF-8. Приложение также принимает UTF-8 BOM и UTF-16 LE/BE.

## 5. Physics glTF

```powershell
& ".\tools\bin\source2\cs2mb-source2.exe" phys `
  --input "$TEMP\world_physics.vmdl_c" `
  --output "$TEMP\world_physics_physics.gltf"
```

Появятся:

```text
<TEMP>\world_physics_physics.gltf
<TEMP>\world_physics_physics.bin
```

Координаты остаются в Hammer units/Source axes. `.bin` обязателен.

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
