import { Page } from '@playwright/test'

export interface Cue {
  index: number
  startMs: number
  text: string
}

/**
 * Субтитры-оверлей: рисует плашку `#pw-caption` внизу страницы и параллельно
 * копит тайминги реплик — из них на teardown собирается сайдкар `.srt`.
 * Плашка вшивается в кадр видео сама собой, отдельного прожига не требует.
 * Переживает навигацию (page.goto): восстанавливается на событии `load`.
 */
export class Captioner {
  private cues: Cue[] = []
  private readonly t0: number
  private last: string | null = null

  constructor(private page: Page) {
    // Момент старта ≈ создание страницы/контекста (когда началась запись видео).
    this.t0 = Date.now()
    page.on('load', () => {
      if (this.last) this.render(this.last).catch(() => {})
    })
  }

  private async render(text: string): Promise<void> {
    await this.page.evaluate((t) => {
      let el = document.getElementById('pw-caption')
      if (!el) {
        el = document.createElement('div')
        el.id = 'pw-caption'
        Object.assign(el.style, {
          position: 'fixed',
          left: '0',
          right: '0',
          bottom: '0',
          zIndex: '2147483647',
          padding: '14px 24px',
          background: 'rgba(15,17,22,0.82)',
          color: '#fff',
          font: '600 20px/1.4 -apple-system, "Segoe UI", Roboto, sans-serif',
          textAlign: 'center',
          letterSpacing: '0.2px',
          pointerEvents: 'none',
          textShadow: '0 1px 3px rgba(0,0,0,0.6)',
        } as CSSStyleDeclaration)
        document.body.appendChild(el)
      }
      el.textContent = t
    }, text)
  }

  async say(text: string): Promise<void> {
    this.cues.push({ index: this.cues.length + 1, startMs: Date.now() - this.t0, text })
    this.last = text
    await this.render(text)
  }

  /** Подержать текущий кадр (чтобы субтитр успел прочитаться). */
  async hold(ms: number): Promise<void> {
    if (ms > 0) await this.page.waitForTimeout(ms)
  }

  dump(): Cue[] {
    return this.cues
  }
}

function srtTime(ms: number): string {
  const h = Math.floor(ms / 3_600_000)
  const m = Math.floor((ms % 3_600_000) / 60_000)
  const s = Math.floor((ms % 60_000) / 1000)
  const mmm = ms % 1000
  const p2 = (n: number) => String(n).padStart(2, '0')
  return `${p2(h)}:${p2(m)}:${p2(s)},${String(mmm).padStart(3, '0')}`
}

/** Реплики → SRT. Конец каждой = старт следующей; у последней — +tailMs. */
export function cuesToSrt(cues: Cue[], tailMs = 2500): string {
  return cues
    .map((c, i) => {
      const end = i + 1 < cues.length ? cues[i + 1].startMs : c.startMs + tailMs
      return `${c.index}\n${srtTime(c.startMs)} --> ${srtTime(end)}\n${c.text}\n`
    })
    .join('\n')
}
