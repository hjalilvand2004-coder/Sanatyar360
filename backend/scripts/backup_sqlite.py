#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""پشتیبان سازگار و آنلاین از SQLite — فاز اعتماد v1.1.0.

کپی سادهٔ فایل SQLite هنگام فعالیت ممکن است ناسازگار باشد (تراکنش‌های باز)؛
این اسکریپت با API رسمی backup دیتابیس، یک snapshot سازگار و کامل می‌سازد.

مصرف:
  python3 backup_sqlite.py [--db مسیر/sanatyar360.db] [--out مسیر/backup.db]
پیش‌فرض: پایگاه کنار اسکریپت/برنامه؛ خروجی کنار آن با مُهر زمان.
"""
import argparse
import os
import sqlite3
import sys
import time


def backup(db_path: str, out_path: str) -> str:
    if not os.path.exists(db_path):
        print(f"پایگاه داده یافت نشد: {db_path}", file=sys.stderr)
        sys.exit(1)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    src = sqlite3.connect(db_path)
    dst = sqlite3.connect(out_path)
    try:
        with dst:
            src.backup(dst)   # snapshot سازگار حتی حین فعالیت برنامه
    finally:
        src.close()
        dst.close()
    size = os.path.getsize(out_path)
    print(f"پشتیبان ساخته شد: {out_path} ({size / 1024:.1f} KB)")
    return out_path


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_db = os.path.join(os.path.dirname(here), "sanatyar360.db")
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("SQLITE_DB", default_db))
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    out = args.out or os.path.join(os.path.dirname(args.db), f"backup-{stamp}.db")
    backup(args.db, out)


if __name__ == "__main__":
    main()
