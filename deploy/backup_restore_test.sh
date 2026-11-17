#!/usr/bin/env bash
# AC-14 — آزمون واقعی پشتیبان‌گیری و بازیابی
# استفاده: در سرور استقرار، از پوشه deploy اجرا کنید
set -e

DB_CONT=${DB_CONT:-$(docker compose ps -q db)}
TEST_DB="uiis_restore_test"
DUMP="/tmp/uiis_backup_test.sql"

echo "== 1) پشتیبان‌گیری کامل =="
docker compose exec -T db pg_dump -U uiis uiis > "$DUMP"
echo "   حجم دامپ: $(du -h "$DUMP" | cut -f1)"

echo "== 2) بازیابی روی دیتابیس آزمایشی =="
docker compose exec -T db psql -U uiis -c "DROP DATABASE IF EXISTS $TEST_DB;"
docker compose exec -T db psql -U uiis -c "CREATE DATABASE $TEST_DB;"
docker compose exec -T db psql -U uiis -d "$TEST_DB" < "$DUMP" > /dev/null

echo "== 3) مقایسه تعداد رکوردهای جداول کلیدی =="
COUNT_ORIG=$(docker compose exec -T db psql -U uiis -t -c "SELECT count(*) FROM industrial_problems;")
COUNT_REST=$(docker compose exec -T db psql -U uiis -d "$TEST_DB" -t -c "SELECT count(*) FROM industrial_problems;")
echo "   industrial_problems: اصلی=$COUNT_ORIG بازیابی=$COUNT_REST"
if [ "$COUNT_ORIG" == "$COUNT_REST" ]; then
  echo "✅ بازیابی موفق — AC-14 تایید شد"
else
  echo "❌ بازیابی ناقص است"
  exit 1
fi
docker compose exec -T db psql -U uiis -c "DROP DATABASE IF EXISTS $TEST_DB;"
