import { expect, test, type Page } from '@playwright/test';

/** The 3–4 minute defense scenario from docs/DEFENSE.md, end to end. */

async function demoLogin(page: Page, name: string) {
  await page.getByRole('button', { name: 'Режим защиты ↗' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('button', { name: new RegExp(name) }).click();
  await expect(page).toHaveURL(/\/(dashboard|team)/);
}

test('student books, mentor confirms, both complete, quiz and review', async ({ page }) => {
  const errors: string[] = [];
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
  page.on('pageerror', (e) => errors.push(e.message));

  await page.goto('/');
  await demoLogin(page, 'Аликхан');

  await page.goto('/mentors/2');
  await page
    .locator('button', { hasText: /\d{2}:\d{2}/ })
    .first()
    .click();
  await page.getByRole('dialog').locator('textarea').fill('Хочу понять LEFT JOIN');
  await page.getByRole('button', { name: /Отправить заявку/ }).click();
  await expect(page).toHaveURL(/\/lessons\//);
  const lesson = new URL(page.url()).pathname;
  await expect(page.getByText('Ожидает подтверждения')).toBeVisible();

  await demoLogin(page, 'Аяулым');
  await page.goto(lesson);
  await page.getByPlaceholder('https://…').fill('https://meet.example.org/e2e');
  await page.getByRole('button', { name: /Подтвердить заявку/ }).click();
  await expect(page.getByRole('link', { name: /Открыть встречу/ })).toBeVisible();
  await page.getByRole('button', { name: /Демо: встреча завершена/ }).click();
  await expect(page.getByText('Студент подтвердит итог.')).toBeVisible();

  await demoLogin(page, 'Аликхан');
  await page.goto(lesson);
  await page.getByRole('button', { name: /Подтверждаю завершение/ }).click();
  await expect(page.getByText('СОСТОЯЛОСЬ ✓')).toBeVisible();

  await page.getByRole('button', { name: /Тест после встречи/ }).click();
  const quiz = page.getByRole('dialog');
  await expect(quiz.locator('fieldset.question')).toHaveCount(3);
  for (const question of await quiz.locator('fieldset.question').all())
    await question.locator('label').first().click();
  await quiz.getByRole('button', { name: /Проверить ответы/ }).click();
  await expect(quiz.locator('.quiz-score')).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('dialog')).toHaveCount(0);

  await page.getByRole('button', { name: /Оставить отзыв/ }).click();
  await page.getByRole('button', { name: '5 из 5' }).click();
  await page.getByLabel('Что помогло разобраться?').fill('Понятно объяснила LEFT JOIN');
  await page.getByRole('button', { name: /Сохранить отзыв/ }).click();
  await expect(page.getByText('«Понятно объяснила LEFT JOIN»')).toBeVisible();

  // Survives a reload: state lives in SQLite, the address in the URL.
  await page.reload();
  await expect(page.getByText('«Понятно объяснила LEFT JOIN»')).toBeVisible();
  expect(errors).toEqual([]);
});

test('password reset page is reachable from login', async ({ page }) => {
  await page.goto('/login');
  await page.getByText('Забыли пароль?').click();
  await expect(page).toHaveURL(/\/reset/);
  await expect(page.getByRole('heading', { name: 'Новый пароль по коду' })).toBeVisible();
});
