import { defineConfig, devices } from '@playwright/test'

/**
 * Конфиг скилла video-walkthrough.
 *
 * Демо: webServer поднимает статическое демо-приложение (scenarios/demo) через
 * python3 -m http.server. В реальном проекте здесь поднимают фронт+бэк на
 * ОТДЕЛЬНЫХ портах с seed-данными (см. закомментированный пример ниже), чтобы не
 * конфликтовать с рабочим сервером разработчика.
 *
 * Проекты Playwright:
 *  - fast  — прогон без записи (проверка «зелёно/красно»);
 *  - video — slowMo + запись webm + субтитры-оверлей → mp4 в videos/.
 */

const PORT = 5250
const APP = `http://localhost:${PORT}`

export default defineConfig({
  testDir: './scenarios',
  outputDir: './.artifacts',
  timeout: 90_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: APP,
    viewport: { width: 1280, height: 800 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: {
    command: `python3 -m http.server ${PORT} --directory scenarios/demo`,
    url: APP,
    reuseExistingServer: false,
    timeout: 30_000,
  },

  // --- Пример для реального приложения (фронт+бэк, seed, отдельные порты) ---
  // webServer: [
  //   {
  //     command: `.venv/bin/uvicorn main:app --port 8799`,
  //     cwd: path.resolve(__dirname, '../server'),
  //     env: { APP_DATA_ROOT: path.resolve(__dirname, 'seed') },
  //     url: 'http://localhost:8799/health',
  //     reuseExistingServer: false,
  //   },
  //   {
  //     command: `npm run dev -- --port 5199 --strictPort`,
  //     cwd: path.resolve(__dirname, '../web'),
  //     env: { API_TARGET: 'http://localhost:8799' },
  //     url: 'http://localhost:5199',
  //     reuseExistingServer: false,
  //   },
  // ],
  // globalSetup: './lib/reset-seed.ts',  // сброс изменяемого слоя seed перед прогоном

  projects: [
    {
      name: 'fast',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'video',
      use: {
        ...devices['Desktop Chrome'],
        video: { mode: 'on', size: { width: 1280, height: 800 } },
        launchOptions: { slowMo: 300 }, // действия видны глазу; читаемость даёт удержание субтитра 5 с
      },
    },
  ],
})
