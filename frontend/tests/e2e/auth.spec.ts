import { expect, test } from '@playwright/test';

// 環境変数から取得(本番パスワードを git に残さない)
// 例: E2E_ADMIN_EMAIL=... E2E_ADMIN_PASSWORD=... npx playwright test
const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? 'pfkbn172@gmail.com';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'TempPassword123!';

test.describe('Auth flow', () => {
  test('login -> dashboard -> logout', async ({ page }) => {
    await page.goto('/marketer/');
    await expect(page).toHaveURL(/\/marketer\/login/);
    await expect(page.getByRole('heading', { name: 'AIウェブマーケター' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'ログイン' })).toBeVisible();

    await page.getByLabel('メールアドレス').fill(ADMIN_EMAIL);
    await page.getByLabel('パスワード').fill(ADMIN_PASSWORD);
    await page.getByRole('button', { name: 'ログイン' }).click();

    // ダッシュボードへ遷移
    await expect(page).toHaveURL(/\/marketer\/?$/);
    await expect(page.getByText('AI 引用回数')).toBeVisible();
    await expect(page.getByText('オーガニックセッション')).toBeVisible();
    await expect(page.getByText(ADMIN_EMAIL)).toBeVisible();

    // ログアウト
    await page.getByRole('button', { name: 'ログアウト' }).click();
    await expect(page).toHaveURL(/\/marketer\/login/);
  });

  test('wrong password shows error message', async ({ page }) => {
    await page.goto('/marketer/login');
    await page.getByLabel('メールアドレス').fill(ADMIN_EMAIL);
    await page.getByLabel('パスワード').fill('definitely-wrong-password');
    await page.getByRole('button', { name: 'ログイン' }).click();
    await expect(
      page.getByText('メールアドレスまたはパスワードが違います'),
    ).toBeVisible();
  });

  test('access protected route redirects to login when unauthenticated', async ({
    page,
    context,
  }) => {
    await context.clearCookies();
    await page.goto('/marketer/');
    await expect(page).toHaveURL(/\/marketer\/login/);
  });
});
