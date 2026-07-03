import { Page, Locator, expect } from '@playwright/test'
import { test } from './fixtures'
import { Captioner } from './caption'

/** Минимальное время субтитра на экране в видео-режиме (мс). */
const STEP_HOLD_MS = Number(process.env.STEP_HOLD_MS ?? 5000)

function isVideoMode(): boolean {
  try { return test.info().project.name === 'video' } catch { return false }
}

/**
 * Шаг сценария: показывает субтитр + оборачивает действие в test.step.
 * Текст = строка Gherkin = заголовок в отчёте = субтитр на видео.
 *
 * В видео-режиме субтитр держится на экране не меньше STEP_HOLD_MS (по умолч.
 * 5 с) — чтобы человек успел прочитать. Быстрые шаги «дотягиваются» до минимума;
 * длинные (перетаскивание и т.п.) и так дольше. Для очень длинных подписей порог
 * растёт (≈60 мс/символ). В fast-режиме удержаний нет — прогон быстрый.
 */
export function step(cap: Captioner, text: string, body: () => Promise<void>): Promise<void> {
  return test.step(text, async () => {
    const t0 = Date.now()
    await cap.say(text)
    await body()
    if (isVideoMode()) {
      const need = Math.max(STEP_HOLD_MS, text.length * 60)
      await cap.hold(need - (Date.now() - t0))
    }
  })
}

/**
 * Открыть приложение по пути и дождаться готовности. `ready` — локатор/селектор,
 * появление которого означает, что страница загрузилась.
 */
export async function openApp(
  page: Page,
  urlPath: string,
  ready: string | Locator,
): Promise<void> {
  await page.goto(urlPath)
  const loc = typeof ready === 'string' ? page.locator(ready) : ready
  await expect(loc.first()).toBeVisible()
}

/**
 * Выделить текст от одного элемента к другому настоящим drag'ом мыши — на видео
 * видно живое выделение. Триггерит нативный mouseup, на который завязана логика
 * выделения в вебе (window.getSelection). `from`/`to` — селекторы или локаторы.
 */
export async function dragSelect(
  page: Page,
  from: string | Locator,
  to: string | Locator,
): Promise<void> {
  const a = (typeof from === 'string' ? page.locator(from) : from).first()
  const b = (typeof to === 'string' ? page.locator(to) : to).first()
  await a.scrollIntoViewIfNeeded()
  const ra = await a.boundingBox()
  const rb = await b.boundingBox()
  if (!ra || !rb) throw new Error('dragSelect: не найдены граничные элементы')

  const y0 = ra.y + ra.height / 2
  const y1 = rb.y + rb.height / 2
  await page.mouse.move(ra.x + 3, y0)
  await page.mouse.down()
  const n = 10
  for (let i = 1; i <= n; i++) {
    const x = ra.x + 3 + ((rb.x + rb.width - 3) - (ra.x + 3)) * (i / n)
    const y = y0 + (y1 - y0) * (i / n)
    await page.mouse.move(x, y)
  }
  await page.mouse.move(rb.x + rb.width - 3, y1)
  await page.mouse.up()
}
