#!/usr/bin/env python3
"""Озвучка walkthrough-видео по его .srt-субтитрам.

Использование:
    python3 lib/narrate.py videos                # все .mp4 с парным .srt
    python3 lib/narrate.py videos/example.mp4    # одно видео
    python3 lib/narrate.py videos --engine say   # принудительно движок
    python3 lib/narrate.py videos --lang en      # принудительно язык

Язык (--lang auto|ru|en, по умолчанию auto) определяется по субтитрам каждого
видео отдельно: кириллицы больше — русский, иначе английский. Русский конвейер
(RUAccent, accents.json, runorm) для английского пропускается — там он не нужен.

Движки (--engine auto|silero|edge|say):
    silero — локальная нейросеть, офлайн, детерминированно; SSML-паузы и
             смысловые акценты из sidecar-файла <видео>.speech.json
    edge   — нейроголоса Microsoft (Svetlana), «качественная озвучка»:
             живая интонация из коробки, но облако и неофициальный API
    say    — macOS `say -v Milena`, без установки
    auto   — silero, если доступен torch (в т.ч. через venv скилла), иначе say

Sidecar смысловых акцентов (только silero): <видео>.speech.json —
{"текст субтитра": {"emphasis": ["ключевое слово", …]}, …}
Ключевые слова читаются чуть медленнее с микропаузами вокруг.

Видео перезаписывается на месте (аудиодорожка заменяется целиком, так что
повторный прогон идемпотентен). Токенов не тратит — чистое выполнение кода.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# venv с torch для Silero, создаётся при разовой настройке скилла
SILERO_VENV_PYTHON = Path.home() / ".claude/skills/video-walkthrough/.venv/bin/python"

SILERO_MODEL = {"ru": "v4_ru", "en": "v3_en"}
SILERO_SPEAKER = {"ru": "xenia", "en": "en_0"}
SILERO_SAMPLE_RATE = 48000
EDGE_VOICE = {"ru": "ru-RU-SvetlanaNeural", "en": "en-US-AriaNeural"}
SAY_VOICE = {"ru": "Milena", "en": "Samantha"}
SAY_RATE = 180  # слов/мин
MAX_ATEMPO = 2.0  # предел ускорения фразы, не влезающей в свой слот


def parse_srt(path: Path):
    """[(start_ms, end_ms, text), ...]"""
    cues = []
    blocks = re.split(r"\n\s*\n", path.read_text(encoding="utf-8").strip())
    for block in blocks:
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        m = re.match(
            r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)",
            lines[1] if lines[0].strip().isdigit() else lines[0],
        )
        if not m:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, m.groups())
        start = ((h1 * 60 + m1) * 60 + s1) * 1000 + ms1
        end = ((h2 * 60 + m2) * 60 + s2) * 1000 + ms2
        text_lines = lines[2:] if lines[0].strip().isdigit() else lines[1:]
        text = " ".join(text_lines).strip()
        if text:
            cues.append((start, end, text))
    return cues


def detect_lang(cues) -> str:
    """Язык озвучки по субтитрам видео: кириллицы больше латиницы — ru, иначе en.
    Латинские термины внутри русских фраз (Whisper, PDF) детект не сбивают."""
    text = " ".join(t for _, _, t in cues)
    cyr = len(re.findall(r"[а-яё]", text, re.I))
    lat = len(re.findall(r"[a-z]", text, re.I))
    return "ru" if cyr >= lat else "en"


def _reexec_into_venv():
    """Зависимости живут в venv скилла — перезапускаемся в него один раз."""
    if SILERO_VENV_PYTHON.exists() and not os.environ.get("NARRATE_REEXEC"):
        os.environ["NARRATE_REEXEC"] = "1"
        os.execv(str(SILERO_VENV_PYTHON), [str(SILERO_VENV_PYTHON)] + sys.argv)


def pick_engine(requested: str) -> str:
    if requested == "say":
        return "say"
    if requested == "edge":
        try:
            import edge_tts  # noqa: F401
            return "edge"
        except ImportError:
            _reexec_into_venv()
            sys.exit("edge недоступен — поставь голосовой стек: bash setup.sh")
    try:
        import torch  # noqa: F401
        return "silero"
    except ImportError:
        _reexec_into_venv()
    if requested == "silero":
        sys.exit("silero недоступен — поставь голосовой стек: bash setup.sh")
    print("  ℹ голосового стека нет, озвучиваю системным голосом. "
          "Для нормального голоса: bash setup.sh")
    return "say"


_accentizer = None
_accent_dict = None


def load_accent_dict() -> dict:
    """Словарь произношений: глобальный из скилла + проектный override рядом с
    местом запуска (`./lib/accents.json` или `./accents.json` относительно cwd —
    проектная лексика перекрывает глобальную). Ищем по cwd, а не по `__file__`,
    чтобы override работал и когда зовём глобальный narrate.py из проекта.
    Ключи — термины как в субтитрах, значения — как читать (кириллицей,
    `+` перед ударной гласной)."""
    global _accent_dict
    if _accent_dict is None:
        _accent_dict = {}
        seen = set()
        for p in (Path.home() / ".claude/skills/video-walkthrough/lib/accents.json",
                  Path.cwd() / "lib" / "accents.json",
                  Path.cwd() / "accents.json"):
            p = p.resolve()
            if p in seen or not p.exists():
                continue
            seen.add(p)
            _accent_dict.update(json.loads(p.read_text(encoding="utf-8")))
    return _accent_dict


def _seconds_form(num: str) -> str:
    """секунда/секунды/секунд по правилам согласования с числом."""
    if "." in num or "," in num:
        return "секунды"  # дробь: «ноль запятая пять секунды»
    n = int(num) % 100
    if 11 <= n <= 14:
        return "секунд"
    return {1: "секунда", 2: "секунды", 3: "секунды", 4: "секунды"}.get(
        n % 10, "секунд")


_runorm = None


def _normalize_latin(fragment: str) -> str:
    """Незнакомая латиница: транслитерация runorm (small) по токенам —
    страховка от молчаливого выпадения слов. Точное произношение терминов
    задаёт accents.json, он применяется раньше и имеет приоритет."""
    tokens = {t.rstrip("+./_-") for t in
              re.findall(r"[A-Za-z][A-Za-z0-9+./_-]*", fragment)}
    tokens.discard("")
    if not tokens:
        return fragment
    global _runorm
    if _runorm is None:
        try:
            from runorm import RUNorm
            _runorm = RUNorm()
            _runorm.load(model_size="small", device="cpu",
                         workdir=str(Path.home()
                                     / ".claude/skills/video-walkthrough/.runorm"))
        except ImportError:
            _runorm = False
    if not _runorm:
        return fragment
    for tok in sorted(tokens, key=len, reverse=True):
        out = _runorm.norm(tok).strip()
        # подменяем, только если латиницы не осталось (иначе пусть предупредит)
        if out and not re.search(r"[A-Za-z]", out):
            fragment = fragment.replace(tok, out)
            print(f"  ℹ {tok} → «{out}» (runorm; точнее — записью в accents.json)")
    return fragment


def _auto_accent(fragment: str) -> str:
    """Числа словами + автоударения RUAccent для «обычного» текста."""
    # «с» после числа — секунды, а не предлог; «±» RUAccent молча съедает
    fragment = re.sub(r"(\d+(?:[.,]\d+)?)\s*с\b",
                      lambda m: f"{m.group(1)} {_seconds_form(m.group(1))}",
                      fragment)
    fragment = fragment.replace("±", " плюс-минус ")
    try:
        from num2words import num2words
        fragment = re.sub(
            r"\d+[.,]\d+",
            lambda m: num2words(float(m.group().replace(",", ".")), lang="ru"),
            fragment)
        fragment = re.sub(r"\d+",
                          lambda m: num2words(int(m.group()), lang="ru"),
                          fragment)
    except ImportError:
        pass
    fragment = _normalize_latin(fragment)
    global _accentizer
    if _accentizer is None:
        try:
            from ruaccent import RUAccent
            _accentizer = RUAccent()
            _accentizer.load(omograph_model_size="turbo", use_dictionary=True)
        except ImportError:
            _accentizer = False
    core = fragment.strip()
    if _accentizer and core and re.search(r"[а-яё]", core, re.I):
        lead = fragment[: len(fragment) - len(fragment.lstrip())]
        trail = fragment[len(fragment.rstrip()):]
        fragment = lead + _accentizer.process_all(core) + trail
    return fragment


def speech_text(text: str, lang: str = "ru") -> str:
    """Готовит текст для синтеза (субтитры не трогает). Silero понимает `+`
    перед ударной гласной, а латиницу и цифры молча выбрасывает — поэтому:
    словарные термины подставляются как есть (и защищены от RUAccent, который
    стирает чужие `+` и переупрямливает слова), остальное получает
    автоударения и числа словами.

    Для en весь русский конвейер пропускается: только числа словами
    (silero en тоже молча выбрасывает цифры)."""
    text = text.replace("·", ".")  # маркер темы → пауза в речи
    if lang == "en":
        try:
            from num2words import num2words
            text = re.sub(
                r"\d+[.,]\d+",
                lambda m: num2words(float(m.group().replace(",", ".")), lang="en"),
                text)
            text = re.sub(r"\d+",
                          lambda m: num2words(int(m.group()), lang="en"),
                          text)
        except ImportError:
            pass
        return text
    d = load_accent_dict()
    if not d:
        result = _auto_accent(text)
    else:
        keys = sorted(d, key=len, reverse=True)
        by_lower = {k.lower(): v for k, v in d.items()}
        splitter = re.compile(
            "(" + "|".join(rf"(?<!\w){re.escape(k)}(?!\w)" for k in keys) + ")",
            re.IGNORECASE,
        )
        parts = splitter.split(text)
        # нечётные индексы — словарные совпадения, их RUAccent не касается
        result = "".join(
            by_lower[p.lower()] if i % 2 else _auto_accent(p)
            for i, p in enumerate(parts)
        )

    leftover = set(re.findall(r"[A-Za-z]{2,}[\w./-]*", result))
    if leftover:
        print(f"  ⚠ латиница без произношения (Silero её пропустит), "
              f"добавьте в accents.json: {', '.join(sorted(leftover))}")
    return result


def build_ssml(text: str, emphasis=(), lang: str = "ru") -> str:
    """SSML для silero: паузы по пунктуации + смысловые акценты.
    Ключевые слова читаются медленнее с микропаузами — эмуляция emphasis,
    которого у Silero нет. Каждый фрагмент проходит speech_text отдельно."""
    from xml.sax.saxutils import escape

    parts = [(False, text)]
    for phrase in emphasis:
        splitted = []
        for is_emph, frag in parts:
            if is_emph:
                splitted.append((is_emph, frag))
                continue
            pieces = re.split(f"({re.escape(phrase)})", frag,
                              flags=re.IGNORECASE)
            splitted += [(i % 2 == 1, p) for i, p in enumerate(pieces) if p]
        parts = splitted

    out = []
    for is_emph, frag in parts:
        s = escape(speech_text(frag, lang))
        s = s.replace("—", '<break time="350ms"/>')
        s = re.sub(r":\s", ':<break time="250ms"/> ', s)
        if is_emph:
            s = (f'<break time="150ms"/><prosody rate="slow">{s}</prosody>'
                 f'<break time="100ms"/>')
        out.append(s)
    return "<speak>" + "".join(out) + "</speak>"


_silero_models = {}


def synth_silero(text: str, out_wav: Path, emphasis=(), lang: str = "ru"):
    import torch
    import wave

    if lang not in _silero_models:
        _silero_models[lang], _ = torch.hub.load(
            "snakers4/silero-models", "silero_tts",
            language=lang, speaker=SILERO_MODEL[lang], trust_repo=True,
        )
    audio = _silero_models[lang].apply_tts(
        ssml_text=build_ssml(text, emphasis, lang), speaker=SILERO_SPEAKER[lang],
        sample_rate=SILERO_SAMPLE_RATE
    )
    pcm = (audio.clamp(-1, 1) * 32767).to(torch.int16).numpy().tobytes()
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SILERO_SAMPLE_RATE)
        w.writeframes(pcm)


def edge_text(text: str, lang: str = "ru") -> str:
    """Подготовка текста для edge: словарь произношений применяется как
    простая подмена текста (Svetlana читает «мэнэджэр» как написано),
    `+`-разметка ударений отбрасывается — edge её не понимает, а SSML-фонемы
    через edge-tts не работают. RUAccent/числа/runorm не нужны — голос сам.
    Для en словарь не применяется: он про русское произношение латиницы."""
    text = text.replace("·", ".")
    if lang == "en":
        return text
    d = load_accent_dict()
    for key in sorted(d, key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(key)}(?!\w)",
                      d[key].replace("+", ""), text, flags=re.IGNORECASE)
    return text


def synth_edge(text: str, out_mp3: Path, lang: str = "ru"):
    """Нейроголос Microsoft: сам интонирует по смыслу, читает латиницу
    и числа; словарь произношений применяется текстовой подменой."""
    import asyncio
    import edge_tts
    asyncio.run(
        edge_tts.Communicate(edge_text(text, lang),
                             EDGE_VOICE[lang]).save(str(out_mp3)))


def synth_say(text: str, out_aiff: Path, lang: str = "ru"):
    subprocess.run(
        ["say", "-v", SAY_VOICE[lang], "-r", str(SAY_RATE),
         "-o", str(out_aiff), text],
        check=True,
    )


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def narrate(video: Path, engine: str, lang_arg: str = "auto") -> bool:
    srt = video.with_suffix(".srt")
    if not srt.exists():
        print(f"  пропуск: нет {srt.name}")
        return False
    cues = parse_srt(srt)
    if not cues:
        print(f"  пропуск: {srt.name} пуст")
        return False
    lang = lang_arg if lang_arg != "auto" else detect_lang(cues)

    sidecar = {}
    sidecar_path = video.with_suffix(".speech.json")
    if sidecar_path.exists():
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))

    video_dur = probe_duration(video)
    ext = {"silero": "wav", "edge": "mp3", "say": "aiff"}[engine]
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clips = []
        for i, (start, end, text) in enumerate(cues):
            clip = tmp / f"cue{i}.{ext}"
            if engine == "silero":
                meta = sidecar.get(text, {})
                emphasis = meta.get("emphasis", []) if isinstance(meta, dict) else meta
                synth_silero(text, clip, emphasis, lang)
            elif engine == "edge":
                synth_edge(text, clip, lang)
            else:
                synth_say(text, clip, lang)
            clips.append((start, end, text, clip))

        # Каждая фраза: ресемпл в моно 48к, ужатие в свой слот, сдвиг на start.
        inputs, chains, labels = [], [], []
        for i, (start, end, text, clip) in enumerate(clips):
            audio_dur = probe_duration(clip)
            slot = (end - start) / 1000
            tempo = 1.0
            if audio_dur > slot:
                tempo = min(audio_dur / slot, MAX_ATEMPO)
                if audio_dur / tempo > slot + 0.3:
                    print(f"  ⚠ фраза {i + 1} длиннее слота даже с ускорением "
                          f"x{MAX_ATEMPO}: «{text}» — увеличьте STEP_HOLD_MS")
            inputs += ["-i", str(clip)]
            chains.append(
                f"[{i + 2}:a]aresample=48000,aformat=channel_layouts=mono,"
                f"atempo={tempo:.4f},adelay={max(start, 1)}:all=1[a{i}]"
            )
            labels.append(f"[a{i}]")

        n = len(clips) + 1  # + тишина-подложка длиной с видео
        filter_graph = (
            ";".join(chains)
            + f";[1:a]{''.join(labels)}amix=inputs={n}:duration=first:normalize=0[mix]"
        )
        out = tmp / "out.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-i", str(video),
             "-f", "lavfi", "-t", f"{video_dur:.3f}",
             "-i", "anullsrc=r=48000:cl=mono",
             *inputs,
             "-filter_complex", filter_graph,
             "-map", "0:v", "-map", "[mix]",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
             "-movflags", "+faststart",  # moov в начало — плеер стартует сразу
             str(out)],
            check=True,
        )
        out.replace(video)
    print(f"  ✓ {video.name}: озвучено {len(cues)} фраз ({engine}, {lang})")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", help=".mp4 или каталог с .mp4+.srt")
    ap.add_argument("--engine", choices=["auto", "silero", "edge", "say"],
                    default="auto")
    ap.add_argument("--lang", choices=["auto", "ru", "en"], default="auto",
                    help="язык озвучки; auto — по субтитрам каждого видео")
    args = ap.parse_args()

    target = Path(args.target)
    videos = sorted(target.glob("*.mp4")) if target.is_dir() else [target]
    if not videos:
        sys.exit(f"нет .mp4 в {target}")

    engine = pick_engine(args.engine)
    print(f"движок: {engine}")
    done = sum(narrate(v, engine, args.lang) for v in videos)
    print(f"готово: {done}/{len(videos)}")


if __name__ == "__main__":
    main()
