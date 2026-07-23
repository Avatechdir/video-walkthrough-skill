import { test, expect } from '../lib/fixtures'
import { step, openApp } from '../lib/steps'

// Английский эталонный сценарий: язык субтитров (и озвучки) задаётся языком
// шагов, скилл менять не нужно. Файл → ролик videos/example-en.mp4;
// narrate.py определит язык по .srt и возьмёт английский голос.

test('example-en · adding a task', async ({ page, cap }) => {
  await step(cap, 'Skill demo: adding a task to the list', async () => {
    await openApp(page, '/?lang=en', '[data-testid="task-input"]')
  })

  await step(cap, 'Type the text of a new task', async () => {
    await page.getByTestId('task-input').fill('Record a video walkthrough')
  })

  await step(cap, 'Click "Add"', async () => {
    await page.getByTestId('add').click()
  })

  await step(cap, 'Done: the task appears in the list', async () => {
    await expect(page.getByTestId('task-row').first()).toContainText('Record a video walkthrough')
  })
})
