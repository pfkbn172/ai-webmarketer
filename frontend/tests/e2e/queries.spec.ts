import { expect, test } from '@playwright/test';

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? 'pfkbn172@gmail.com';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'TempPassword123!';

test.describe('Target Queries page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/marketer/login');
    await page.getByLabel('メールアドレス').fill(ADMIN_EMAIL);
    await page.getByLabel('パスワード').fill(ADMIN_PASSWORD);
    await page.getByRole('button', { name: 'ログイン' }).click();
    await expect(page.getByText('AI 引用回数')).toBeVisible();
  });

  test('navigate to queries page and add then delete', async ({ page }) => {
    await page.getByRole('link', { name: 'ターゲットクエリ' }).click();
    await expect(page).toHaveURL(/\/marketer\/queries/);

    const uniqueQuery = `e2e-test-${Date.now()}`;
    await page.getByPlaceholder(/新しいクエリを入力/).fill(uniqueQuery);
    await page.getByRole('button', { name: '追加' }).click();

    await expect(page.getByText(uniqueQuery)).toBeVisible();

    // 同じ行の削除ボタンをクリック
    const row = page
      .locator('li')
      .filter({ hasText: uniqueQuery });
    await row.getByRole('button', { name: '削除' }).click();
    await expect(page.getByText(uniqueQuery)).not.toBeVisible();
  });
});
