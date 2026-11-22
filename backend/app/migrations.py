"""helper مهاجرت — اجرای upgrade از داخل برنامه (سرور) با منطق stamp خودکار.

در نسخهٔ پرتیبل (FROZEN) مهاجرت اجرا نمی‌شود؛ آنجا create_all روی پایگاه
تازهٔ خودش انجام می‌شود (entry پرتیبل). در استقرار سرور، این helper صدا زده
می‌شود تا اسکیما همیشه نسخه‌دار و به‌روز باشد.

پایگاه‌های پیشین (ساخته‌شده با create_all و بدون alembic_version):
  فقط «stamp» به سرِ نسخهٔ اولیه انجام می‌شود؛ چون اسکیمای فعلی همان نسخهٔ
  اولیه است و اجرای مهاجرت روی آن خطای جدول‌موجود می‌دهد.
"""
import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from .core.config import FROZEN, settings

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def alembic_config() -> Config:
    cfg = Config(os.path.join(BACKEND_DIR, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(BACKEND_DIR, "migrations"))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return cfg


def migrations_enabled() -> bool:
    return (not FROZEN) and os.environ.get("DATABASE_MIGRATE", "1") == "1" \
        and os.path.isdir(os.path.join(BACKEND_DIR, "migrations", "versions"))


def _is_legacy_db() -> bool:
    """جدول‌ها موجودند اما رد مهاجرت (alembic_version) نیست."""
    engine = create_engine(settings.database_url)
    try:
        tables = inspect(engine).get_table_names()
        return bool(tables) and "alembic_version" not in tables
    except Exception:
        return False
    finally:
        engine.dispose()


def run_upgrade_head() -> str | None:
    """upgrade head با پشتیبانی از پایگاه‌های پیشین (stamp خودکار). خروجی: پیام وضعیت."""
    if not migrations_enabled():
        return None
    try:
        if _is_legacy_db():
            command.stamp(alembic_config(), "head")
            return "migrations: legacy database stamped at head"
        command.upgrade(alembic_config(), "head")
        return "migrations: upgrade head OK"
    except Exception as exc:  # شکست مهاجرت مانع بالا آمدن نمی‌شود؛ در لاگ دیده می‌شود
        return f"migrations: SKIPPED ({exc})"
