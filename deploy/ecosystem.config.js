// PM2 ecosystem (implementation_plan.md 13 章)
//
// 配置:
//   pm2 start /var/www/ai-web-marketer/deploy/ecosystem.config.js
//   pm2 save  # 永続化(systemd の pm2-root.service が次回起動で resurrect)
//
// 既存 pm2-root.service を流用するため、本ファイルは追加プロセスを 1〜2 個だけ登録する。
// 既存サービス(ai-dx-api, DriveWatchWebSocket 等)には一切影響しない。

module.exports = {
  apps: [
    {
      name: 'marketer-api',
      cwd: '/var/www/ai-web-marketer/backend',
      script: '/var/www/ai-web-marketer/backend/.venv/bin/uvicorn',
      args: 'app.main:app --host 127.0.0.1 --port 3009 --workers 2',
      interpreter: 'none', // Python 仮想環境を直接呼ぶため Node interpreter は使わない
      env: {
        PYTHONUNBUFFERED: '1',
      },
      max_memory_restart: '600M',
      autorestart: true,
      watch: false,
      out_file: '/var/log/marketer/api.out.log',
      error_file: '/var/log/marketer/api.err.log',
      merge_logs: true,
      time: true,
    },
    // marketer-worker は W3-01 で APScheduler を本実装してから登録。
    // 現状は entrypoint がまだ未作成のためコメントアウト。
    // {
    //   name: 'marketer-worker',
    //   cwd: '/var/www/ai-web-marketer/backend',
    //   script: '/var/www/ai-web-marketer/backend/.venv/bin/python',
    //   args: '-m app.worker.entrypoint',
    //   interpreter: 'none',
    //   env: { PYTHONUNBUFFERED: '1' },
    //   max_memory_restart: '500M',
    //   autorestart: true,
    //   watch: false,
    //   out_file: '/var/log/marketer/worker.out.log',
    //   error_file: '/var/log/marketer/worker.err.log',
    //   merge_logs: true,
    //   time: true,
    // },
  ],
};
