# video-walkthrough-skill

> 🇷🇺 [Русская версия](README.ru.md) — документация на русском.

**A [Claude Code](https://claude.com/claude-code) skill that turns one
Playwright scenario into an automated test + a video walkthrough with
per-step subtitles.**

The same scenario that verifies your feature is replayed in a browser with
`slowMo`, captioning every step. Clicks are highlighted with a ripple ring at
the pointer, and subtitles can be **narrated with a voice** (Russian or
English — the language is detected from the subtitles). The output is an
`.mp4` (+ `.srt`) that serves both as **proof the feature is tested** and as
**video documentation** for your client/team. A third artifact of the same
scenario is a **bank of clean walkthrough screenshots** (`npm run screens`):
before/after frames of every step for UX/UI analysis.

> One Gherkin scenario = specification + automated test + video script.

## What it looks like

```
step(cap, 'Type the text of a new task', async () => {
  await page.getByTestId('task-input').fill('Record a video walkthrough')
})
```

The step text becomes both the heading in the Playwright report and the
subtitle on the video. Every subtitle stays on screen ≥5 s so a human can
read it. **The video language = the language of your scenario steps**: write
the steps in English and the subtitles and narration come out in English
(reference: `scenarios/example-en.spec.ts`; the Russian twin is
`scenarios/example.spec.ts`).

## Quick start (bundled demo)

Requires Node 18+, `ffmpeg` and `python3` in PATH.

```bash
npm install
npx playwright install chromium

npm test            # fast run, no recording (green/red check)
npm run video       # record → videos/example.mp4 (+ .srt)
npm run video:burn  # same, but subtitles burned into frames via ffmpeg

npm run video:voice     # narrate subtitles (Silero, offline)
npm run video:voice:hq  # same with Microsoft neural voices (livelier, but cloud)

npm run screens     # clean before/after screenshots → screens/<scenario>/
```

Narration is a separate step **on top of a finished `mp4`+`srt` pair**: install
the voice stack once (see [Narration](#narration)) and old videos can be
narrated without re-recording.

The demo app (`scenarios/demo/index.html`) is a simple task list; the
webServer starts it automatically. Prebuilt videos: `videos/example.mp4`
(Russian) and `videos/example-en.mp4` (English).

## What's inside

```
.claude/skills/video-walkthrough/SKILL.md   # instructions for Claude Code
lib/
  caption.ts       # subtitle overlay + .srt assembly (survives navigation)
  click-marker.ts  # click highlight ring at the pointer (video mode)
  record.ts        # webm → mp4 (ffmpeg), .srt sidecar
  fixtures.ts      # cap fixture + video finalization in video mode
  steps.ts         # step() (subtitle+step+hold), openApp(), dragSelect()
  screens.ts       # before/after walkthrough screenshots (SCREENS=1, fast mode)
  narrate.py       # subtitle narration: Silero/edge/say, ru+en, speech preprocessor
  accents.json     # pronunciation dictionary for terms (Russian narration)
  add-accent.py    # word-form generator for accents.json
playwright.config.ts   # webServer + fast|video projects
scenarios/
  example.feature      # human-readable Gherkin (Russian)
  example.spec.ts      # executable scenario (reference to copy)
  example-en.feature   # English reference
  example-en.spec.ts   # English reference (English subtitles and narration)
  demo/index.html      # demo app (?lang=en switches the locale)
```

## Hooking into your project

1. Copy `lib/`, `playwright.config.ts`, `package.json` into a `qa/` directory
   of your repo; copy `.claude/skills/video-walkthrough/` into the repo root.
2. `cd qa && npm install && npx playwright install chromium`.
3. In `playwright.config.ts`, replace the demo `webServer` with your app
   **on dedicated ports with seed data** (a template is in the config comments).
4. Add ~5 `data-testid` attributes to the key nodes of your scenario.
5. Write scenarios `qa/scenarios/US-XX-<slug>.{feature,spec.ts}` following
   `example.*`. File name = video name.

From then on Claude Code picks the skill up on requests like "record a video
walkthrough for US-42".

## Click highlighting

In `video` mode every click is highlighted with an expanding ring and a dot at
the pointer (`lib/click-marker.ts`) — the viewer clearly sees where the
scenario clicked. The marker is injected via `addInitScript`, so it survives
navigation and shows up even if the app swallows the event (capture-phase
listener). It is baked into the frame like the subtitles; fast `npm test` runs
are unaffected.

## Walkthrough screenshots

`npm run screens` replays the same scenarios in fast mode and saves
`NN-before-…png` / `NN-after-…png` frame pairs into `screens/<scenario>/` —
the UI state before and after every step, file names derived from step texts.
The frames are **clean**: no subtitle bar, no click marker (fast mode draws no
overlays). This is a screenshot bank for UX/UI analysis of your product; each
run rewrites the scenario folder entirely, history lives in git.

## Narration

`npm run video:voice` synthesizes speech from the `.srt` and mixes it into the
`mp4` at subtitle timecodes (ffmpeg `adelay`). It works **post-factum on a
finished mp4+srt pair** — the audio track is replaced entirely, so re-running
is idempotent. Pure code execution, no tokens spent.

**Language** is detected per video from its subtitles (`--lang auto|ru|en`):
more Cyrillic → Russian voice, otherwise English. The Russian-specific
preprocessing (stress marks, term dictionary, transliteration) is skipped for
English — it is not needed there.

**Engines** (`--engine auto|silero|edge|say`):

| Engine | Voice ru / en | Pros | Cons |
|---|---|---|---|
| `silero` (default) | `xenia` / `en_0` | offline, deterministic, free | flatter intonation |
| `edge` (`video:voice:hq`) | `Svetlana` / `Aria` | lively intonation out of the box | cloud, unofficial API |
| `say` | macOS `Milena` / `Samantha` | zero install | robotic |

**Speech readability (Russian).** Subtitles stay clean; the text passes a
preprocessor before synthesis: RUAccent stress marks (dictionary + contextual
homographs), numbers and units spelled out, a pronunciation dictionary for
Latin-script terms (`lib/accents.json`), and transliteration fallback (runorm)
so unknown Latin words never silently drop out of the narration.

**Expressiveness (silero).** Punctuation pauses are inserted automatically
(SSML). Semantic emphasis lives in a `<video>.speech.json` sidecar next to the
srt: the given keyword is read slightly slower with micro-pauses. Filled in
while authoring the scenario.

**Voice stack install** — one idempotent command:

```bash
npm run setup
```

Builds the venv, downloads the word-form base and syncs the code into the
global skill copy. Models are cached on first synthesis. Without the stack
`narrate.py` falls back to the system `say` voice.

> Already using the skill without narration? `git pull && npm run setup` —
> details in [UPGRADING.md](UPGRADING.md) (Russian).

## Principles

- **The video is a by-product of the test.** You write the scenario anyway;
  recording is just the `--project=video` flag.
- **Verification is assertions only** (`expect`). The recorded video is never
  analyzed multimodally — expensive and pointless. Video is for humans,
  assertions are for machines.
- **Stable `data-testid`s**, isolated **seed data**, test stand on
  **dedicated ports** — determinism and zero impact on your dev environment.

## Settings

| Variable | Meaning | Default |
|---|---|---|
| `STEP_HOLD_MS` | Minimum subtitle time on screen (ms) | `5000` |
| `BURN_SUBS=1` | Burn `.srt` into frames via ffmpeg | off (overlay) |
| `slowMo` (in config) | Pause between actions for video | `300` ms |
| `--engine` (narrate.py) | Narration engine: `auto`/`silero`/`edge`/`say` | `auto` |
| `--lang` (narrate.py) | Narration language: `auto`/`ru`/`en` | `auto` (from subtitles) |

## License

MIT.
