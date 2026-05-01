"""初期 admin ユーザー作成スクリプト。

使い方:
    cd backend
    .venv/bin/python -m scripts.create_admin_user --email pfkbn172@gmail.com

パスワードは対話式入力(getpass)。標準入力からも読める。
既存ユーザーがいる場合はパスワードのみ更新する(役割変更はしない)。
"""

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.password import hash_password
from app.db.models.enums import UserRoleEnum
from app.db.models.user import User
from app.settings import settings


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", help="指定しない場合は対話入力")
    args = parser.parse_args()

    password = args.password or getpass.getpass("Password: ")
    if len(password) < 8:
        print("[ERROR] パスワードは 8 文字以上にしてください", file=sys.stderr)
        return 2

    engine = create_async_engine(settings.db_dsn)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        existing = (
            await session.scalars(select(User).where(User.email == args.email))
        ).one_or_none()

        if existing:
            existing.password_hash = hash_password(password)
            existing.role = UserRoleEnum.admin
            existing.is_active = True
            print(f"[INFO] {args.email} のパスワードを更新しました")
        else:
            user = User(
                email=args.email,
                password_hash=hash_password(password),
                role=UserRoleEnum.admin,
                is_active=True,
            )
            session.add(user)
            print(f"[INFO] admin ユーザー {args.email} を作成しました")

        await session.commit()

    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
