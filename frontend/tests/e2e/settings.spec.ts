import { expect, test } from '@playwright/test';

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? 'pfkbn172@gmail.com';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'TempPassword123!';

test.describe('Settings page (4 tabs)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/marketer/login');
    await page.getByLabel('メールアドレス').fill(ADMIN_EMAIL);
    await page.getByLabel('パスワード').fill(ADMIN_PASSWORD);
    await page.getByRole('button', { name: 'ログイン' }).click();
    await expect(page.getByText('AI 引用回数')).toBeVisible();
  });

  test('navigate through all 4 tabs', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 1024 });
    await page.getByRole('link', { name: '設定' }).click();
    await expect(page).toHaveURL(/\/marketer\/settings/);

    // タブ A: 著者
    await expect(page.getByRole('heading', { name: '著者プロフィール' })).toBeVisible();
    await page.screenshot({ path: 'test-results/screen-settings-authors.png', fullPage: true });

    // タブ B: 競合
    await page.getByRole('button', { name: '競合' }).click();
    await expect(page.getByRole('heading', { name: '競合ドメイン' })).toBeVisible();
    await page.screenshot({ path: 'test-results/screen-settings-competitors.png', fullPage: true });

    // タブ C: WordPress
    await page.getByRole('button', { name: 'WordPress 連携' }).click();
    await expect(page.getByRole('heading', { name: 'WordPress 連携' })).toBeVisible();
    await page.screenshot({ path: 'test-results/screen-settings-wordpress.png', fullPage: true });

    // タブ D: API キー
    await page.getByRole('button', { name: 'API キー', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'AI Provider / 外部 API キー' })).toBeVisible();
    await page.screenshot({ path: 'test-results/screen-settings-apikeys.png', fullPage: true });
  });
});

test.describe('Citation manual page', () => {
  test('open and screenshot', async ({ page }) => {
    await page.goto('/marketer/login');
    await page.getByLabel('メールアドレス').fill(ADMIN_EMAIL);
    await page.getByLabel('パスワード').fill(ADMIN_PASSWORD);
    await page.getByRole('button', { name: 'ログイン' }).click();
    await expect(page.getByText('AI 引用回数')).toBeVisible();

    await page.getByRole('link', { name: '手入力' }).click();
    await expect(page.getByRole('heading', { name: '引用モニタ 手入力' })).toBeVisible();
    await expect(page.getByText('LLM を開く')).toBeVisible();
    await page.setViewportSize({ width: 1280, height: 1024 });
    await page.screenshot({ path: 'test-results/screen-citation-manual.png', fullPage: true });
  });
});

test.describe('Inquiries page', () => {
  test('open and capture form', async ({ page }) => {
    await page.goto('/marketer/login');
    await page.getByLabel('メールアドレス').fill(ADMIN_EMAIL);
    await page.getByLabel('パスワード').fill(ADMIN_PASSWORD);
    await page.getByRole('button', { name: 'ログイン' }).click();
    await expect(page.getByText('AI 引用回数')).toBeVisible();

    await page.getByRole('link', { name: '問い合わせ' }).click();
    await expect(page.getByRole('heading', { name: '問い合わせログ' })).toBeVisible();

    await page.getByRole('button', { name: '+ 手動で問い合わせを追加' }).click();
    await expect(page.getByRole('heading', { name: '問い合わせを手動入力' })).toBeVisible();
    await page.setViewportSize({ width: 1280, height: 1024 });
    await page.screenshot({ path: 'test-results/screen-inquiries.png', fullPage: true });
  });
});
