import { test, expect } from '../lib/fixtures'
import { step, openApp } from '../lib/steps'

// Эталонный сценарий скилла. Тестирует демо-приложение (scenarios/demo/index.html),
// которое поднимает webServer из playwright.config. Имя файла example.spec.ts →
// ролик videos/example.mp4.

test('example · добавление задачи', async ({ page, cap }) => {
  await step(cap, 'Пример скилла: добавляем задачу в список', async () => {
    // Навигация в первом шаге — экран не пустует; субтитр переживёт переход.
    await openApp(page, '/', '[data-testid="task-input"]')
  })

  await step(cap, 'Вводим текст новой задачи', async () => {
    await page.getByTestId('task-input').fill('Записать видео-инструкцию')
  })

  await step(cap, 'Нажимаем «Добавить»', async () => {
    await page.getByTestId('add').click()
  })

  await step(cap, 'Готово: задача появилась в списке', async () => {
    await expect(page.getByTestId('task-row').first()).toContainText('Записать видео-инструкцию')
  })
})
