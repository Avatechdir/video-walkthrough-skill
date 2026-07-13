#!/usr/bin/env bash
# Одноразовая (и идемпотентная) настройка озвучки.
#   bash setup.sh
# Ставит голосовой стек, скачивает базу словоформ и — если запущен из
# репозитория скилла — синхронизирует код в глобальную копию
# ~/.claude/skills/video-walkthrough. Безопасно запускать повторно.
set -euo pipefail

SKILL_DIR="$HOME/.claude/skills/video-walkthrough"
VENV="$SKILL_DIR/.venv"
WORDS="$SKILL_DIR/lib/russian-words.txt"
HERE="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$SKILL_DIR/lib"

# 1. Синхронизация кода (только если запущены из репозитория со свежими файлами)
if [ -f "$HERE/lib/click-marker.ts" ]; then
  echo "→ синхронизирую код в $SKILL_DIR"
  cp -r "$HERE/lib" "$HERE/package.json" "$SKILL_DIR/"
  [ -f "$HERE/.claude/skills/video-walkthrough/SKILL.md" ] \
    && cp "$HERE/.claude/skills/video-walkthrough/SKILL.md" "$SKILL_DIR/SKILL.md"
  echo "  ✓ код обновлён"
fi

# 2. Голосовой стек в venv (путь захардкожен в narrate.py — именно сюда)
if [ ! -x "$VENV/bin/python" ]; then
  echo "→ создаю venv: $VENV"
  python3 -m venv "$VENV"
fi
echo "→ ставлю голосовой стек (torch, ruaccent, edge-tts… — до ~2 ГБ при первом разе)"
"$VENV/bin/pip" install --quiet --upgrade pip
"$VENV/bin/pip" install --quiet \
  torch omegaconf numpy ruaccent "transformers<5" num2words runorm edge-tts
echo "  ✓ голосовой стек готов"

# 3. База словоформ (для add-accent.py; большая, вне git)
if [ ! -f "$WORDS" ]; then
  echo "→ качаю базу словоформ…"
  curl -sL https://raw.githubusercontent.com/danakt/russian-words/master/russian.txt \
    | iconv -f windows-1251 -t utf-8 > "$WORDS"
fi
echo "  ✓ база словоформ на месте ($(wc -l < "$WORDS" | tr -d ' ') слов)"

echo
echo "готово. Проверка:  npm run video:voice   (ждём «движок: silero»)"
echo "клик-эффект в видео появляется при пере­записи:  npm run video"
