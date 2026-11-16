import { expect, test, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';

async function demoLogin(page: Page, name: string) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Режим защиты ↗' }).click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: new RegExp(name) })
    .click();
  await expect(page).toHaveURL(/\/(dashboard|team)/);
}

test('propose and accept a new time, then download .ics', async ({ page }) => {
  await demoLogin(page, 'Аликхан');
  await page.goto('/mentors/2');
  await page
    .locator('button', { hasText: /\d{2}:\d{2}/ })
    .first()
    .click();
  await page.getByRole('dialog').locator('textarea').fill('Перенос');
  await page.getByRole('button', { name: /Отправить заявку/ }).click();
  await expect(page).toHaveURL(/\/lessons\//);
  const lesson = new URL(page.url()).pathname;

  await page.getByRole('button', { name: /Предложить другое время/ }).click();
  const options = page.locator('.reschedule-options button');
  const chosen = (await options.last().textContent())!.trim();
  await options.last().click();
  await expect(page.getByText('Предложено новое время')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Отозвать предложение' })).toBeVisible();

  await demoLogin(page, 'Аяулым');
  await page.goto(lesson);
  await page.getByRole('button', { name: 'Перенести', exact: true }).click();
  await expect(page.getByText('Предложено новое время')).toHaveCount(0);
  await expect(page.getByText(chosen.split(',')[0])).toBeVisible();

  await page.getByPlaceholder('https://…').fill('https://meet.example.org/e2e-ics');
  await page.getByRole('button', { name: /Подтвердить заявку/ }).click();
  const [file] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: /Добавить в календарь/ }).click(),
  ]);
  const ics = readFileSync((await file.path())!, 'utf8');
  expect(ics).toContain('BEGIN:VCALENDAR');
  expect(ics).toContain('SEQUENCE:1');
  expect(ics).toContain('URL:https://meet.example.org/e2e-ics');
});
