import { expect, test } from '@playwright/test';

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? 'pfkbn172@gmail.com';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'TempPassword123!';

test.describe('Manual page', () => {
  test('navigate to manual and capture snapshot', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 1024 });

    // login
    await page.goto('/marketer/login');
    await page.getByLabel('メールアドレス').fill(ADMIN_EMAIL);
    await page.getByLabel('パスワード').fill(ADMIN_PASSWORD);
    await page.getByRole('button', { name: 'ログイン' }).click();
    await expect(page.getByText('AI 引用回数')).toBeVisible();

    // navigate to manual
    await page.getByRole('link', { name: 'マニュアル' }).click();
    await expect(page).toHaveURL(/\/marketer\/manual/);

    // 主要セクションが表示されるか
    await expect(
      page.getByRole('heading', { name: '1. このシステムは何をするのか' }),
    ).toBeVisible();
    await expect(page.getByRole('heading', { name: '5. 日々の使い方(週次運用フロー)' })).toBeVisible();

    // 目次のリンクで該当セクションへスクロール
    await page.locator('a[href="#data-flow"]').click();
    await expect(
      page.getByRole('heading', { name: '3. データの流れ・更新頻度' }),
    ).toBeVisible();

    // フルページスクリーンショット保存
    await page.screenshot({ path: 'test-results/screen-manual.png', fullPage: true });
  });
});
