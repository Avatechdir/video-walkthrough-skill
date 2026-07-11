import { test as base } from '@playwright/test'
import { Captioner } from './caption'
import { installClickMarker } from './click-marker'
import { finalizeVideo } from './record'

/**
 * Базовый test с фикстурой `cap` (субтитры). В режиме `video` после каждого
 * теста конвертирует запись в mp4 + srt; клики подсвечиваются кольцом.
 */
export const test = base.extend<{ cap: Captioner }>({
  cap: async ({ page }, use, testInfo) => {
    if (testInfo.project.name === 'video') await installClickMarker(page)
    await use(new Captioner(page))
  },
})

test.afterEach(async ({ page, cap }, testInfo) => {
  if (testInfo.project.name === 'video') {
    await finalizeVideo(page, cap, testInfo)
  }
})

export { expect } from '@playwright/test'
