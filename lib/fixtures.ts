import { test as base } from '@playwright/test'
import { Captioner } from './caption'
import { installClickMarker } from './click-marker'
import { finalizeVideo } from './record'

/**
 * Базовый test с фикстурой `cap` (субтитры). В режиме `video` клики
 * подсвечиваются кольцом, а teardown фикстуры конвертирует запись в mp4 + srt.
 *
 * ВАЖНО: финализация живёт в teardown фикстуры, а НЕ в test.afterEach на уровне
 * модуля — модуль кэшируется на воркер, и afterEach регистрировался бы только
 * для первого spec-файла (остальные оставались бы без mp4).
 */
export const test = base.extend<{ cap: Captioner }>({
  cap: async ({ page }, use, testInfo) => {
    const video = testInfo.project.name === 'video'
    if (video) await installClickMarker(page)
    const cap = new Captioner(page, video)
    await use(cap)
    if (video) await finalizeVideo(page, cap, testInfo)
  },
})

export { expect } from '@playwright/test'
