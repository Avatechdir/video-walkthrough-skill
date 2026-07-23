import { Page, TestInfo } from '@playwright/test'
import { mkdir, rm } from 'fs/promises'
import path from 'path'

const SCREENS_DIR = path.resolve(__dirname, '..', 'screens')

/**
 * Скриншоты прохода: при SCREENS=1 fast-прогон складывает пары кадров
 * до/после каждого шага в screens/<имя-сценария>/. Кадры чистые (без плашки
 * субтитра и маркера клика) — банк для UX/UI-анализа по запросу.
 * В video-режиме выключено: там кадры замусорены оверлеями, есть само видео.
 */
export function screensEnabled(testInfo: TestInfo): boolean {
  return process.env.SCREENS === '1' && testInfo.project.name !== 'video'
}

/** Имя каталога = имя spec-файла без `.spec.ts` (как у видео). */
function scenarioDir(testInfo: TestInfo): string {
  const base = path.basename(testInfo.file).replace(/\.spec\.[tj]s$/, '')
  return path.join(SCREENS_DIR, base || 'scenario')
}

/** Текст шага → безопасное имя файла (кириллица остаётся). */
function slugify(text: string): string {
  return (
    text
      .toLowerCase()
      .replace(/[^\p{L}\p{N}]+/gu, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60) || 'шаг'
  )
}

const counters = new Map<string, number>()
const prepared = new Set<string>()

/** Порядковый номер шага в рамках теста (для префикса NN- в имени файла). */
export function nextStepIndex(testInfo: TestInfo): number {
  const n = (counters.get(testInfo.testId) ?? 0) + 1
  counters.set(testInfo.testId, n)
  return n
}

/**
 * Снять кадр шага. Каталог сценария перед первым кадром прогона очищается
 * целиком — набор файлов детерминирован, историю ведёт git.
 * Ошибка съёмки не роняет тест: скрины — побочный артефакт, не проверка.
 */
export async function shotStep(
  page: Page,
  testInfo: TestInfo,
  index: number,
  phase: 'before' | 'after',
  text: string,
): Promise<void> {
  const dir = scenarioDir(testInfo)
  if (!prepared.has(dir)) {
    await rm(dir, { recursive: true, force: true })
    await mkdir(dir, { recursive: true })
    prepared.add(dir)
  }
  const name = `${String(index).padStart(2, '0')}-${phase}-${slugify(text)}.png`
  try {
    // animations: 'disabled' — проматывает CSS-анимации/transition к финалу,
    // иначе кадр «после» ловит появление попапов на полупрозрачной фазе.
    await page.screenshot({ path: path.join(dir, name), animations: 'disabled' })
  } catch (e) {
    // eslint-disable-next-line no-console
    console.warn(`  ⚠ скриншот не снят (${name}): ${(e as Error).message}`)
  }
}
