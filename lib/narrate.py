#!/usr/bin/env python3
"""Озвучка walkthrough-видео по его .srt-субтитрам.

Использование:
    python3 lib/narrate.py videos                # все .mp4 с парным .srt
    python3 lib/narrate.py videos/example.mp4    # одно видео
    python3 lib/narrate.py videos --engine say   # принудительно движок

Движки (--engine auto|silero|say):
    silero — локальная нейросеть, лучший русский (нужен: pip install torch)
    say    — macOS `say -v Milena`, без установки
    auto   — silero, если доступен torch, иначе say

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

SILERO_SPEAKER = "xenia"
SILERO_SAMPLE_RATE = 48000
SAY_VOICE = "Milena"
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


def pick_engine(requested: str) -> str:
    if requested == "say":
        return "say"
    try:
        import torch  # noqa: F401
        return "silero"
    except ImportError:
        pass
    # torch нет в текущем интерпретаторе — перезапускаемся в venv скилла
    if SILERO_VENV_PYTHON.exists() and not os.environ.get("NARRATE_REEXEC"):
        os.environ["NARRATE_REEXEC"] = "1"
        os.execv(str(SILERO_VENV_PYTHON), [str(SILERO_VENV_PYTHON)] + sys.argv)
    if requested == "silero":
        sys.exit("silero недоступен: нет torch и нет venv "
                 f"({SILERO_VENV_PYTHON})")
    return "say"


_accentizer = None
_accent_dict = None


def load_accent_dict() -> dict:
    """Словарь произношений: глобальный из скилла + локальный рядом со скриптом
    (локальный имеет приоритет). Ключи — термины как в субтитрах, значения —
    как их читать (кириллицей, `+` перед ударной гласной)."""
    global _accent_dict
    if _accent_dict is None:
        _accent_dict = {}
        for p in (Path.home() / ".claude/skills/video-walkthrough/lib/accents.json",
                  Path(__file__).resolve().parent / "accents.json"):
            if p.exists():
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


def speech_text(text: str) -> str:
    """Готовит текст для синтеза (субтитры не трогает). Silero понимает `+`
    перед ударной гласной, а латиницу и цифры молча выбрасывает — поэтому:
    словарные термины подставляются как есть (и защищены от RUAccent, который
    стирает чужие `+` и переупрямливает слова), остальное получает
    автоударения и числа словами."""
    text = text.replace("·", ".")  # маркер темы → пауза в речи
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


_silero_model = None


def synth_silero(text: str, out_wav: Path):
    global _silero_model
    import torch
    import wave

    if _silero_model is None:
        _silero_model, _ = torch.hub.load(
            "snakers4/silero-models", "silero_tts",
            language="ru", speaker="v4_ru", trust_repo=True,
        )
    audio = _silero_model.apply_tts(
        text=speech_text(text), speaker=SILERO_SPEAKER,
        sample_rate=SILERO_SAMPLE_RATE
    )
    pcm = (audio.clamp(-1, 1) * 32767).to(torch.int16).numpy().tobytes()
    with wave.open(str(out_wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SILERO_SAMPLE_RATE)
        w.writeframes(pcm)


def synth_say(text: str, out_aiff: Path):
    subprocess.run(
        ["say", "-v", SAY_VOICE, "-r", str(SAY_RATE), "-o", str(out_aiff), text],
        check=True,
    )


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def narrate(video: Path, engine: str) -> bool:
    srt = video.with_suffix(".srt")
    if not srt.exists():
        print(f"  пропуск: нет {srt.name}")
        return False
    cues = parse_srt(srt)
    if not cues:
        print(f"  пропуск: {srt.name} пуст")
        return False

    video_dur = probe_duration(video)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        clips = []
        for i, (start, end, text) in enumerate(cues):
            clip = tmp / (f"cue{i}.wav" if engine == "silero" else f"cue{i}.aiff")
            (synth_silero if engine == "silero" else synth_say)(text, clip)
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
             str(out)],
            check=True,
        )
        out.replace(video)
    print(f"  ✓ {video.name}: озвучено {len(cues)} фраз ({engine})")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", help=".mp4 или каталог с .mp4+.srt")
    ap.add_argument("--engine", choices=["auto", "silero", "say"], default="auto")
    args = ap.parse_args()

    target = Path(args.target)
    videos = sorted(target.glob("*.mp4")) if target.is_dir() else [target]
    if not videos:
        sys.exit(f"нет .mp4 в {target}")

    engine = pick_engine(args.engine)
    print(f"движок: {engine}")
    done = sum(narrate(v, engine) for v in videos)
    print(f"готово: {done}/{len(videos)}")


if __name__ == "__main__":
    main()
