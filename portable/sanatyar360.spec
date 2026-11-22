# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — نسخه پرتیبل صنعت‌یار۳۶۰ (onedir)
# ساخت: pyinstaller portable/sanatyar360.spec
# خروجی: dist/Sanatyar360/Sanatyar360(.exe) + پوشه _internal
# onedir به‌جای onefile: سرعت شروع بالاتر و احتمال حذف توسط آنتی‌ویروس بسیار کمتر
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

hiddenimports = [
    "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.loops.asyncio",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.httptools", "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan", "uvicorn.lifespan.on", "uvicorn.lifespan.off",
    "app", "app.main", "app.db", "app.models", "app.serializers",
    "app.core.config", "app.core.security", "app.core.deps",
    "app.routers.auth", "app.routers.sso", "app.routers.orgs", "app.routers.problems",
    "app.routers.applications", "app.routers.matching", "app.routers.collaborations",
    "app.routers.analytics", "app.routers.commercialization", "app.routers.misc",
    "app.routers.assistant", "app.routers.maharat",
    "app.services", "app.services.matching", "app.services.assistant",
    "app.services.team", "app.services.maharat",
    "seed", "anyio._backends._asyncio", "multipart",
]

excludes = [
    "psycopg", "psycopg_binary", "psycopg2", "pgserver",
    "alembic", "celery", "redis", "tkinter", "matplotlib", "numpy",
    "PIL", "pytest", "IPython", "jupyter",
]

a = Analysis(
    [os.path.join(ROOT, "portable", "sanatyar360_entry.py")],
    pathex=[os.path.join(ROOT, "backend")],
    datas=[
        (os.path.join(ROOT, "frontend", "dist"), "webdist"),
    ],
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Sanatyar360",
    console=True,
    upx=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="Sanatyar360",
)
