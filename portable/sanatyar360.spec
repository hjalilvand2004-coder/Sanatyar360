# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec — نسخه پرتیبل صنعت‌یار۳۶۰
# ساخت: pyinstaller portable/sanatyar360.spec
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
    "app.services.matching",
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
    a.binaries,
    a.datas,
    name="sanatyar360",
    console=True,
    upx=False,
    runtime_tmpdir=None,
)
