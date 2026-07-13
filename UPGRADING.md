# Обновление: озвучка, подсветка кликов, препроцессор речи

Если скилл стоял у тебя **без озвучки** — этот гайд добавляет её (плюс подсветку
кликов). Код приезжает с `git pull`, но голосовой движок ставится локально
отдельно — просто обновить репозиторий недостаточно.

## Что нового
- **Озвучка субтитров** — `npm run video:voice` (Silero, офлайн) или
  `npm run video:voice:hq` (голос Microsoft Svetlana). Работает пост-фактум по
  готовой паре `mp4`+`srt`, старые ролики озвучиваются без перезаписи видео.
- **Подсветка кликов** — в записи каждый клик отмечается кольцом в точке нажатия
  (появляется автоматически при следующей записи `npm run video`).
- **Препроцессор речи** — ударения, числа, словарь произношений терминов.

## Шаг 1. Забрать код

```bash
cd <папка-репозитория-скилла>
git pull
```

Это обновит `lib/` (`narrate.py`, `accents.json`, `add-accent.py`,
`click-marker.ts`, `fixtures.ts`), `SKILL.md`, `package.json`, README.

**Дальше зависит от того, как скилл установлен у тебя:**

- **Глобально** (папка в `~/.claude/skills/video-walkthrough/`) — пересинхронизируй
  туда обновлённые файлы из репозитория:
  ```bash
  cp -r lib SKILL.md package.json ~/.claude/skills/video-walkthrough/
  cp .claude/skills/video-walkthrough/SKILL.md ~/.claude/skills/video-walkthrough/SKILL.md
  ```
- **В проекте** (каталог `qa/` внутри рабочего репозитория) — обнови файлы там:
  ```bash
  cp lib/narrate.py lib/accents.json lib/add-accent.py \
     lib/click-marker.ts lib/fixtures.ts <проект>/qa/lib/
  ```
  и допиши в `<проект>/qa/package.json` скрипты `video:voice` и `video:voice:hq`
  (см. `package.json` этого репозитория).

Если не уверена, куда ставила, — сделай оба; лишним не будет.

## Шаг 2. Поставить голосовой стек (разово)

Без него `narrate.py` не упадёт, но озвучит роботизированным системным голосом
`say -v Milena`. Для нормального голоса нужен venv:

```bash
python3 -m venv ~/.claude/skills/video-walkthrough/.venv
~/.claude/skills/video-walkthrough/.venv/bin/pip install \
  torch omegaconf numpy ruaccent "transformers<5" num2words runorm edge-tts
```

Пути в `narrate.py` захардкожены на `~/.claude/skills/video-walkthrough/.venv`,
поэтому venv должен лежать именно там (даже если сам скилл ты используешь из
проектного `qa/`). Модели (~2 ГБ Silero + мелочь) скачаются в кэш при первом
синтезе, дальше работает офлайн.

`torch` требует Python 3.9+. На маке подойдёт `python3` из Homebrew.

## Шаг 3. (Опционально) база словоформ для add-accent.py

Нужна только если будешь пополнять словарь произношений (`add-accent.py`). Файл
большой, в git не хранится:

```bash
curl -sL https://raw.githubusercontent.com/danakt/russian-words/master/russian.txt \
  | iconv -f windows-1251 -t utf-8 \
  > ~/.claude/skills/video-walkthrough/lib/russian-words.txt
```

## Шаг 4. Проверить

Возьми любое видео с парным `.srt` и озвучь:

```bash
npm run video:voice            # Silero (или say, если стек не поставлен)
```

В выводе должно быть `движок: silero` и `✓ … озвучено N фраз`. Если видишь
`движок: say` — venv не подхватился, вернись к шагу 2.

Для «качественной» озвучки голосом Svetlana (нужен интернет):

```bash
npm run video:voice:hq
```

## Если голос читает слово неправильно

Слова с мягким «е» вместо «э» (тег, плеер, менеджер), латиница, аббревиатуры —
это ожидаемо, лечится словарём `lib/accents.json`. Подробности — в разделе
«Озвучка» в [SKILL.md](.claude/skills/video-walkthrough/SKILL.md): там описан
рабочий цикл пополнения словаря и генератор форм `add-accent.py`.
