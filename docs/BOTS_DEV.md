# Как устроены боты BotHub и как их выпускать

## Структура

```
templates/
  catalog.json          ← список ботов для приложения (id, категория, поля, title, zipUrl, sha256, version)
  i18n.py               ← общий модуль языков (ИСХОДНИК)
  pybionic_core.py      ← общее ядро (ИСХОДНИК)
  pybionic_web.py       ← общий дизайн веб-страниц ботов (ИСХОДНИК)
  <bot_id>/
    main.py             ← код бота, функция main()
    locales.json        ← тексты бота {"strings": {key: {ru, en, ...}}, "lists": {...}}
    requirements.txt
    i18n.py, pybionic_core.py, pybionic_web.py   ← КОПИИ, их делает tools/sync_shared.py
                          (pybionic_web.py кладётся только тем ботам, чей main.py его импортирует)
dist/<bot_id>-<version>.zip     ← архивы, которые скачивает приложение
tools/                  ← скрипты (ниже)
```

Приложение ставит бота отдельной папкой, поэтому общие файлы лежат копиями в каждой папке.
Правьте только `templates/i18n.py`, `templates/pybionic_core.py` и `templates/pybionic_web.py`, потом запускайте `tools/sync_shared.py`.

## Общее ядро `pybionic_core.py`

| Что | Зачем |
|---|---|
| `core.guard_bot(bot)` | Сразу после `TeleBot(...)`. Не пускает тех, кого нет в `ALLOWED_USER_IDS` (сообщения, кнопки, inline). `closed_if_empty=True` закрывает бота, если список пуст. |
| `core.download_tg_file(bot, file_id, size)` | Скачивание с понятной ошибкой `core.FileTooBig`, если файл больше 20 МБ (лимит Bot API). |
| `core.run_media(cmd, ...)` | Вместо `subprocess.run` для ffmpeg/sox: общая очередь (`MEDIA_MAX_JOBS`, по умолчанию 1) и таймаут (`MEDIA_TIMEOUT_SEC`, 900 с). Телефон не перегревается от трёх видео сразу. |
| `core.start_janitor([папки])` | Удаляет файлы старше `CLEANUP_HOURS` (48 ч) из кэша. `.db`/`.json` не трогает. `CLEANUP_HOURS=0` выключает. |
| `core.btn(key, uid)` / `core.is_btn(text, key)` | Надпись кнопки на языке пользователя и проверка нажатия на любом языке. Общие кнопки (`btn_lang`, `btn_help`, `btn_menu`, `btn_cancel`, `btn_back`) уже переведены на 24 языка внутри ядра; свои кнопки бота кладите в его `locales.json` с префиксом `kb_`. |
| `core.start_polling(bot, ...)` | Вместо `bot.infinity_polling(...)`: без интернета или при блокировке Telegram бот не падает, а пишет подсказку и повторяет. Прокси — переменная `TELEGRAM_PROXY` (`http://IP:8080` или `socks5h://IP:1080`, для socks нужен `PySocks`). |
| `core.get_data_dir()`, `core.format_bytes()`, `core.format_duration()`, `core.env_int()` | Мелкие помощники. |

## Веб-страницы ботов `pybionic_web.py`

У 26 ботов есть веб-студия (открывается из приложения на `127.0.0.1:<WEB_PORT>`). Все они сделаны на одном модуле,
поэтому выглядят одинаково: стеклянная шапка, анимированный фон, шрифты Onest + Unbounded, тёмная и светлая тема, телефон.

| Что | Зачем |
|---|---|
| `web.resolve_lang(handler)` | Язык страницы: `?lang=` → cookie `pb_lang` → `PYBIONIC_LANG` → `en`. Он отдельный от языка бота в Telegram. |
| `T = web.translator(lang)` | Тексты: сначала ключи из `locales.json` бота (страничные — с префиксом `w_`), потом общие (`COMMON`, 24 языка). |
| `web.send_page(handler, lang, title=, emoji=, brand=, port=, hero_html=, body=, script=)` | Отдать готовую страницу. `brand` — фирменный цвет бота. |
| `web.hero`, `card`, `grid`, `field`, `input_`, `textarea`, `select`, `button`, `segmented`, `toggles`, `range_`, `dropzone`, `progress`, `stats`, `table`, `note`, `empty_state` | Готовые блоки. Всё, что пришло от пользователя, они экранируют сами. |
| JS `pb.*` | `pb.t(key)` перевод, `pb.json/post/postJSON/upload` запросы, `pb.toast`, `pb.progress`, `pb.busy`, `pb.count`, `pb.esc`. |

Новые тексты страницы добавляйте в `locales.json` бота ключами `w_*` сразу на все 24 языка
(`ru, en, tg, uz, tr, es, de, fr, it, pt, pl, uk, kk, ky, az, ar, fa, hi, zh-cn, ja, ko, id, vi, th`).
API-адреса ботов (`/api/...`) при переделке страниц не менялись — кроме `media_downloader`, которому добавлены
`/api/download` (фоновая задача), `/api/job`, `/api/files`, `/api/delete`.

## Выпуск изменений

1. Поправили бота → поднимите его `"version"` в `templates/catalog.json` (например `1.1.0` → `1.1.1`).
2. `python tools/sync_shared.py` — разложить общие файлы.
3. `python tools/build_catalog.py` — собрать `dist/<id>-<version>.zip` и вписать `zipUrl`/`sha256`.
4. `python tools/check_bots.py` — проверить каталог, переводы и импорт всех ботов.
5. Коммит, пуш. GitHub Actions (`.github/workflows/check-bots.yml`) повторит проверки.

Приложение увидит новую версию и предложит обновить бота. `.env`, базы `.db` и папка `data/` пользователя при обновлении сохраняются.

## Новый бот

1. Папка `templates/<id>/` с `main.py` (функция `main()`), `locales.json`, `requirements.txt`.
2. Запись в `catalog.json`: `id`, `category`, `fields`, `title` и `description` (словари языков, минимум `en` и `ru`), `version: "1.0.0"`.
3. Шаги 2–5 выше.

Категории приложения сейчас: `DOWNLOADERS`, `MEDIA_STICKERS`, `PRODUCTIVITY`, `DISCORD_MULTI`.
Незнакомая категория (`UTILITIES`, `BUSINESS`, `AI_ASSISTANTS`, `DEVELOPER_TOOLS`, `MODERATION`) показывается во вкладке «Продуктивность» —
чтобы у них были свои вкладки, добавьте значения в enum категорий приложения.
