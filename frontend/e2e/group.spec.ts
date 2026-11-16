import { expect, test, type Page } from '@playwright/test';

async function demoLogin(page: Page, name: string) {
  await page.goto('/');
  await page.getByRole('button', { name: 'Режим защиты ↗' }).click();
  await page
    .getByRole('dialog')
    .getByRole('button', { name: new RegExp(name) })
    .click();
  await expect(page).toHaveURL(/\/(dashboard|team)/);
}

test('student joins the demo group lesson and sees the other participant', async ({ page }) => {
  await demoLogin(page, 'Аликхан');
  const deadline = Math.floor(Date.now() / 1000) + 5 * 86400;
  await page.goto(
    `/mentors/2?topic_id=1&budget=3000&deadline=${deadline}&language=ru&format=online`,
  );
  const seat = page.locator('.slot-group').first();
  await expect(seat).toContainText('занято 1 из 4');
  await seat.click();
  await expect(page.getByRole('dialog')).toContainText('1 200 ₸');
  await page.getByRole('dialog').locator('textarea').fill('Хочу в группу');
  await page.getByRole('button', { name: /Записаться в группу/ }).click();
  await expect(page).toHaveURL(/\/lessons\//);
  await expect(page.getByText('Запись подтверждена')).toBeVisible();
  await expect(page.getByText('Группа · 2 из 4')).toBeVisible();
  await expect(page.getByText(/Участники: Ерлан, Аликхан/)).toBeVisible();
  await expect(page.getByRole('link', { name: /Открыть встречу/ })).toBeVisible();
});
