#!/usr/bin/env python3
"""Генератор записей accents.json по базе словоформ (danakt/russian-words).

    python3 lib/add-accent.py плеер пл+эер            # показать кандидатов
    python3 lib/add-accent.py плеер пл+эер --apply    # дописать в словарь
    python3 lib/add-accent.py тег т+эг --exclude стратег,стратега --apply

Находит в базе (1,5 млн словоформ) все слова с данным корнем — падежные формы
и композиты («плеер» → «видеоплеером», «медиаплееры»…) — и генерирует записи
с подстановкой произношения корня.

ВСЕГДА просматривай кандидатов перед --apply: поиск по корню цепляет ложные
совпадения («тег» → «стратег», «ихтиостег») — исключай их через --exclude.
"""

import argparse
import json
import re
import sys
from pathlib import Path

SKILL_LIB = Path.home() / ".claude/skills/video-walkthrough/lib"
WORDS_FILE = SKILL_LIB / "russian-words.txt"
DICT_FILE = SKILL_LIB / "accents.json"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", help="корень как в субтитрах, напр. «плеер»")
    ap.add_argument("replacement",
                    help="произношение корня с ударением, напр. «пл+эер»")
    ap.add_argument("--apply", action="store_true",
                    help="дописать записи в глобальный accents.json")
    ap.add_argument("--exclude", default="",
                    help="слова-ложные совпадения через запятую")
    ap.add_argument("--no-compounds", action="store_true",
                    help="корень только в начале слова (для коротких корней "
                         "типа «тег», где композиты — сплошь ложные)")
    args = ap.parse_args()

    if not WORDS_FILE.exists():
        sys.exit(f"нет базы {WORDS_FILE}\nскачать: curl -sL "
                 "https://raw.githubusercontent.com/danakt/russian-words/master/russian.txt"
                 f" | iconv -f windows-1251 -t utf-8 > {WORDS_FILE}")

    root = args.root.lower()
    excluded = {w.strip().lower() for w in args.exclude.split(",") if w.strip()}
    # корень + окончание до 4 букв; допускаем приставку/первую основу композита
    prefix = "" if args.no_compounds else "[а-яё-]*"
    form = re.compile(rf"^({prefix})({re.escape(root)})([а-яё]{{0,4}})$")

    entries = {}
    for word in WORDS_FILE.read_text(encoding="utf-8").split():
        m = form.match(word)
        if m and word not in excluded:
            entries[word] = m.group(1) + args.replacement + m.group(3)

    if not entries:
        sys.exit(f"в базе нет форм с корнем «{root}»")

    for k in sorted(entries):
        print(f'  "{k}": "{entries[k]}"')

    if args.apply:
        d = json.loads(DICT_FILE.read_text(encoding="utf-8"))
        d.update(entries)
        DICT_FILE.write_text(
            json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"→ добавлено {len(entries)} записей в {DICT_FILE}")
    else:
        print("→ просмотри список и повтори с --apply "
              "(ложные корни убери через --exclude)")


if __name__ == "__main__":
    main()
