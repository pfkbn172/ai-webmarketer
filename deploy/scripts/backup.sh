#!/usr/bin/env bash
#
# PostgreSQL バックアップ(日次 + 月初の月次保管)。
#
# RLS バイパス: marketer ロールは FORCE ROW LEVEL SECURITY 配下のテーブルで
# pg_dump が QUERY FAILED を出すため、postgres スーパーユーザーで実行する。
# peer 認証(/etc/postgresql/16/main/pg_hba.conf)前提なのでパスワード不要。
#
# 所有権の整合性のため、cron は pfkbn172 ユーザーの crontab に登録すること。
# /var/backups/marketer は pfkbn172:pfkbn172 / 700 を想定。
#
# リストア検証:
#   pg_restore -l /var/backups/marketer/marketer_daily_<曜日>.dump | head
#   (各テーブルの DDL 行と DATA 行が並べば成功)
set -euo pipefail

DUMPDIR=/var/backups/marketer
DAY=$(date +%a)
DUMPFILE="$DUMPDIR/marketer_daily_${DAY}.dump"

mkdir -p "$DUMPDIR"

# postgres スーパーユーザーで pg_dump(RLS をバイパス)
sudo -u postgres pg_dump -Fc -d marketer > "$DUMPFILE"

# サイズチェック(0 バイトなら明らかに失敗)
SIZE=$(stat -c%s "$DUMPFILE")
if [ "$SIZE" -lt 1024 ]; then
    echo "[ERROR] dump size ${SIZE} bytes is too small" >&2
    exit 1
fi

# 検証: pg_restore -l でアーカイブ目次が読めるか(壊れていれば失敗)
if ! pg_restore -l "$DUMPFILE" > /dev/null 2>&1; then
    echo "[ERROR] pg_restore -l failed: dump may be corrupted" >&2
    exit 1
fi

# 月初(1 日)なら月次バックアップも作成し、13 ヶ月以上前のものを削除
if [ "$(date +%d)" = "01" ]; then
    cp "$DUMPFILE" "$DUMPDIR/marketer_monthly_$(date +%Y%m).dump"
    find "$DUMPDIR" -name 'marketer_monthly_*.dump' -mtime +400 -delete
fi

echo "[$(date -Iseconds)] backup ok: $(basename "$DUMPFILE") (${SIZE} bytes)"
