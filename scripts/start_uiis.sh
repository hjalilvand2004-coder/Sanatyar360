#!/usr/bin/env bash
# راه‌اندازی کامل سامانه تعامل دانشگاه و صنعت (پایگاه داده + API + رابط وب)
# استفاده: bash start_uiis.sh [--reset-db] [--stop]
set -e

PG_BIN=/home/z/.venv/lib/python3.12/site-packages/pgserver/pginstall/bin
export PATH="$PG_BIN:$PATH"
PGDATA=/home/z/my-project/uiis/pgdata
BACKEND=/home/z/my-project/uiis/backend
LOG_DIR=/home/z/my-project/uiis/logs
mkdir -p "$LOG_DIR"

start_postgres() {
  if "$PG_BIN/pg_isready" -h "$PGDATA" -p 5432 >/dev/null 2>&1; then
    echo "postgres already running"
  else
    if [ ! -f "$PGDATA/PG_VERSION" ]; then
      "$PG_BIN/initdb" -D "$PGDATA" -U postgres --auth=trust >/dev/null
      createdb -h "$PGDATA" -U postgres uiis
    fi
    "$PG_BIN/pg_ctl" -D "$PGDATA" -l "$LOG_DIR/postgres.log" start
    "$PG_BIN/psql" -h "$PGDATA" -U postgres -tc "SELECT 1 FROM pg_database WHERE datname='uiis'" | grep -q 1 || \
      "$PG_BIN/psql" -h "$PGDATA" -U postgres -c "CREATE DATABASE uiis"
    echo "postgres started on socket $PGDATA"
  fi
}

stop_all() {
  "$PG_BIN/pg_ctl" -D "$PGDATA" stop -m fast 2>/dev/null || true
  pkill -f "uvicorn.*8092" 2>/dev/null || true
  echo "stopped"
}

case "$1" in
  --stop) stop_all; exit 0 ;;
esac

start_postgres

if [ "$1" == "--reset-db" ]; then
  (cd "$BACKEND" && python3 seed.py --reset)
else
  (cd "$BACKEND" && python3 -c "
from app.db import Base, engine
Base.metadata.create_all(engine)
from app.db import SessionLocal
from app.models import User
import sys
sys.path.insert(0, '.')
db = SessionLocal()
n = db.query(User).count()
db.close()
if n == 0:
    import seed
    seed.main()
" || (cd "$BACKEND" && python3 seed.py))
fi

cd "$BACKEND"
export DATABASE_URL="postgresql+psycopg://postgres@127.0.0.1:5432/uiis"
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8092 --log-level info
