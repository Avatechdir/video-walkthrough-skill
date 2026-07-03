import { Page, TestInfo } from '@playwright/test'
import { execFile } from 'child_process'
import { mkdir, writeFile, rm } from 'fs/promises'
import path from 'path'
import { promisify } from 'util'
import { Captioner, cuesToSrt } from './caption'

const run = promisify(execFile)

const VIDEOS_DIR = path.resolve(__dirname, '..', 'videos')

/** Имя ролика = имя spec-файла без `.spec.ts` (совпадает с .feature). */
function slugFor(testInfo: TestInfo): string {
  const base = path.basename(testInfo.file).replace(/\.spec\.[tj]s$/, '')
  return base || 'scenario'
}

/**
 * Финализация записи (только `--project=video`):
 *  1) дождаться и забрать сырой webm,
 *  2) записать сайдкар `.srt` из таймингов субтитров,
 *  3) ffmpeg webm → mp4 (H.264, faststart). Прожиг SRT — опция BURN_SUBS=1.
 * Плашки-субтитры уже вшиты в кадр, поэтому по умолчанию SRT — только сайдкар.
 * Требует установленного ffmpeg в PATH.
 */
export async function finalizeVideo(page: Page, cap: Captioner, testInfo: TestInfo): Promise<void> {
  const video = page.video()
  if (!video) return

  const slug = slugFor(testInfo)
  await mkdir(VIDEOS_DIR, { recursive: true })

  // Закрываем страницу, чтобы запись финализировалась, затем забираем webm.
  await page.close()
  const rawWebm = path.join(testInfo.outputDir, 'raw.webm')
  await video.saveAs(rawWebm)

  const srtPath = path.join(VIDEOS_DIR, `${slug}.srt`)
  await writeFile(srtPath, cuesToSrt(cap.dump()), 'utf-8')

  const mp4Path = path.join(VIDEOS_DIR, `${slug}.mp4`)
  const burn = process.env.BURN_SUBS === '1'
  const vf = burn
    ? ['-vf', `subtitles=${srtPath}:force_style='FontSize=18,Outline=1,MarginV=24'`]
    : []

  await run('ffmpeg', [
    '-y',
    '-i', rawWebm,
    ...vf,
    '-c:v', 'libx264',
    '-pix_fmt', 'yuv420p',
    '-movflags', '+faststart',
    mp4Path,
  ])

  await rm(rawWebm, { force: true })

  testInfo.attachments.push({ name: 'video-mp4', path: mp4Path, contentType: 'video/mp4' })
  // eslint-disable-next-line no-console
  console.log(`  🎬 видео: videos/${slug}.mp4  (+ ${slug}.srt)`)
}
