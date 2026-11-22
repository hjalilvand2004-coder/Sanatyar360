"""محیط Alembic — اتصال به تنظیمات برنامه صنعت‌یار۳۶۰.

آدرس پایگاه داده: اولویت با sqlalchemy.url در Config برنامه‌ای؛ در نبود آن از
تنظیمات سامانه (DATABASE_URL) خوانده می‌شود.

منطق «stamp خودکار پایگاه پیشین» عمداً اینجا نیست (باز اجرای env.py در حین
stamp باعث حلقه می‌شود)؛ در app/migrations.py → run_upgrade_head() انجام می‌شود.
"""
import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402
from app.db import Base  # noqa: E402
import app.models  # noqa: F401,E402  (ثبت همهٔ مدل‌ها در metadata)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", settings.database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata,
                          compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
