import { expect, test } from '@playwright/test';

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL ?? 'pfkbn172@gmail.com';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD ?? 'TempPassword123!';

async function login(page: any) {
  await page.goto('/marketer/login');
  await page.getByLabel('メールアドレス').fill(ADMIN_EMAIL);
  await page.getByLabel('パスワード').fill(ADMIN_PASSWORD);
  await page.getByRole('button', { name: 'ログイン' }).click();
  await expect(page.getByText('AI 引用回数')).toBeVisible();
}

test('strategic review page renders', async ({ page }) => {
  await login(page);
  await page.getByRole('link', { name: '戦略レビュー', exact: true }).click();
  await expect(page).toHaveURL(/\/marketer\/strategic/);
  // ページタイトルの「戦略レビュー」と Card の AI 戦略レビューが両方マッチするため
  // exact ではなく、違和感アラートの見出しの存在で代用
  await expect(page.getByRole('heading', { name: '違和感アラート(自動検知)' })).toBeVisible();
  await expect(
    page.getByRole('heading', { name: 'AI 戦略レビュー(月次レポートと別、いつでも実行可能)' }),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: '戦略軸 A/B 比較' })).toBeVisible();
  await expect(
    page.getByRole('heading', { name: '競合パターン分析(citation_logs 頻出ドメイン)' }),
  ).toBeVisible();
  await page.setViewportSize({ width: 1280, height: 1400 });
  await page.screenshot({ path: 'test-results/screen-strategic.png', fullPage: true });
});

test('settings has business context tab with AI hearing', async ({ page }) => {
  await login(page);
  await page.getByRole('link', { name: '設定' }).click();
  await expect(page.getByRole('button', { name: '事業情報 (戦略の根拠)' })).toBeVisible();
  await page.getByRole('button', { name: '事業情報 (戦略の根拠)' }).click();
  await expect(
    page.getByRole('heading', { name: '✨ AI に質問して埋めてもらう' }),
  ).toBeVisible();
  await expect(page.getByRole('heading', { name: '事業基本情報' })).toBeVisible();
  await page.setViewportSize({ width: 1280, height: 1400 });
  await page.screenshot({ path: 'test-results/screen-settings-business.png', fullPage: true });
});

test('queries page has AI suggest button', async ({ page }) => {
  await login(page);
  await page.getByRole('link', { name: 'クエリ' }).click();
  await expect(
    page.getByRole('heading', { name: '✨ AI にクエリを提案させる' }),
  ).toBeVisible();
  await expect(
    page.getByRole('button', { name: 'AI に 15〜20 本提案させる' }),
  ).toBeVisible();
  await page.setViewportSize({ width: 1280, height: 1400 });
  await page.screenshot({ path: 'test-results/screen-queries-ai.png', fullPage: true });
});
