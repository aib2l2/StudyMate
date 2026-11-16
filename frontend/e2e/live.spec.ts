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

test('chat message reaches the other participant live, without reload', async ({ browser }) => {
  const studentCtx = await browser.newContext();
  const mentorCtx = await browser.newContext();
  const student = await studentCtx.newPage();
  const mentor = await mentorCtx.newPage();

  await demoLogin(student, 'Аликхан');
  await student.goto('/mentors/2');
  await student
    .locator('button', { hasText: /\d{2}:\d{2}/ })
    .first()
    .click();
  await student.getByRole('dialog').locator('textarea').fill('Чат-проверка');
  await student.getByRole('button', { name: /Отправить заявку/ }).click();
  await expect(student).toHaveURL(/\/lessons\//);
  const lesson = new URL(student.url()).pathname;

  await demoLogin(mentor, 'Аяулым');
  await mentor.goto(lesson);
  await expect(mentor.getByText('Сообщений пока нет', { exact: false })).toBeVisible();

  const box = student.getByLabel('Сообщение', { exact: false });
  await box.fill('Можно начать с LEFT JOIN?');
  await box.press('Enter');
  await expect(
    student.locator('.chat-own', { hasText: 'Можно начать с LEFT JOIN?' }),
  ).toBeVisible();

  const started = Date.now();
  await expect(mentor.getByText('Можно начать с LEFT JOIN?')).toBeVisible({ timeout: 3000 });
  expect(Date.now() - started).toBeLessThan(3000);
  await expect(student.getByText('Прочитано')).toBeVisible({ timeout: 5000 });

  await studentCtx.close();
  await mentorCtx.close();
});
