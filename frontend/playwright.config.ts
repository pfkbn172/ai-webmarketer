import { defineConfig, devices } from '@playwright/test';

// 本番デプロイ済みの /marketer/ に対する実機 E2E テスト。
// /etc/hosts に 127.0.0.1 app.kiseeeen.co.jp を追加してあるので、
// ブラウザはそのホスト名で 127.0.0.1 にアクセスし、Nginx の Host 一致が動く。
// 自己署名/Let's Encrypt 証明書のエラーは ignoreHTTPSErrors で許可。
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 60_000,
  retries: 0,
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: 'https://app.kiseeeen.co.jp',
    ignoreHTTPSErrors: true,
    trace: 'on-first-retry',
    video: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
