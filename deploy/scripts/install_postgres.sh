#!/usr/bin/env bash
#
# PostgreSQL 16 を apt でインストールし、本プロジェクト専用の DB / ロール / 拡張を作成する。
#
# Ubuntu 24.04 標準リポジトリの postgresql は 16.x。PGDG リポジトリは使わない(標準で十分)。
# 既存 MySQL とは別ポート(5432)・別データディレクトリで競合しない。
#
# 前提:
# - root または sudo 可能なユーザーで実行
# - 環境変数 MARKETER_DB_PASSWORD が設定されていること(空ならスクリプト内で生成)
#
# 実行例:
#   MARKETER_DB_PASSWORD="$(openssl rand -hex 24)" sudo -E bash deploy/scripts/install_postgres.sh
#
# 冪等性:
# - 既にインストール済みの postgresql-16 はスキップ
# - 既存ロール / DB / 拡張は CREATE OR REPLACE 相当の判定でスキップ

set -euo pipefail

PG_MAJOR=16
DB_NAME="marketer"
DB_USER="marketer"

if [[ -z "${MARKETER_DB_PASSWORD:-}" ]]; then
  echo "[WARN] MARKETER_DB_PASSWORD が未設定。ランダム生成します。"
  MARKETER_DB_PASSWORD="$(openssl rand -hex 24)"
  echo "[INFO] 生成パスワード: ${MARKETER_DB_PASSWORD}"
  echo "[INFO] このパスワードを .env の MARKETER_DB_DSN に反映してください。"
fi

echo "[1/4] apt update + postgresql-${PG_MAJOR} インストール"
apt-get update -qq
apt-get install -y postgresql-${PG_MAJOR} postgresql-contrib-${PG_MAJOR}

echo "[2/4] postgresql サービス有効化・起動"
systemctl enable --now postgresql

echo "[3/4] DB / ロール / 拡張作成"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE ROLE ${DB_USER} LOGIN PASSWORD '${MARKETER_DB_PASSWORD}';
  ELSE
    ALTER ROLE ${DB_USER} WITH PASSWORD '${MARKETER_DB_PASSWORD}';
  END IF;
END
\$\$;
SQL

# CREATE DATABASE はトランザクション外で実行する必要がある
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
  sudo -u postgres createdb -O ${DB_USER} ${DB_NAME}
  echo "[INFO] DB '${DB_NAME}' を作成しました。"
else
  echo "[INFO] DB '${DB_NAME}' は既に存在します。スキップ。"
fi

sudo -u postgres psql -d ${DB_NAME} -v ON_ERROR_STOP=1 <<SQL
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
SQL

echo "[4/4] 動作確認"
sudo -u postgres psql -d ${DB_NAME} -c "\dx"

echo ""
echo "[DONE] PostgreSQL ${PG_MAJOR} セットアップ完了。"
echo "       DB: ${DB_NAME} / USER: ${DB_USER} / HOST: 127.0.0.1 / PORT: 5432"
