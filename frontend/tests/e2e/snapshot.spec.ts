/**
 * 全画面のスクリーンショットを取得して、目視確認(/開発時のレグレッション検出用)。
 */
import { test } from '@playwright/test';

const ADMIN_EMAIL = 'pfkbn172@gmail.com';
const ADMIN_PASSWORD = 'TempPassword123!';

test.describe('Snapshots', () => {
  test('capture all screens', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });

    // login
    await page.goto('/marketer/login');
    await page.screenshot({ path: 'test-results/screen-login.png', fullPage: true });

    await page.getByLabel('メールアドレス').fill(ADMIN_EMAIL);
    await page.getByLabel('パスワード').fill(ADMIN_PASSWORD);
    await page.getByRole('button', { name: 'ログイン' }).click();

    // dashboard
    await page.waitForURL(/\/marketer\/?$/);
    await page.waitForTimeout(500);
    await page.screenshot({ path: 'test-results/screen-dashboard.png', fullPage: true });

    // queries
    await page.getByRole('link', { name: 'ターゲットクエリ' }).click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: 'test-results/screen-queries.png', fullPage: true });

    // citations
    await page.getByRole('link', { name: 'AI 引用モニタ' }).click();
    await page.waitForTimeout(300);
    await page.screenshot({ path: 'test-results/screen-citations.png', fullPage: true });
  });
});
