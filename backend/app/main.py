"""صنعت‌یار۳۶۰ — اتصال دانشجو به صنعت | زیرسیستم دانشجو۳۶۰ | FastAPI monolithic modular"""
import os
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .db import Base, engine
from .routers import (
    analytics, applications, assistant, auth, collaborations, commercialization,
    maharat, matching, misc, orgs, problems, sso,
)

app = FastAPI(
    title=settings.app_name,
    version="1.1.0-portable",
    description="بستر مدیریت چرخه تعامل دانشگاه و صنعت: ثبت مسئله ← بررسی و انتشار ← تطبیق ← همکاری ← دستاورد",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # در پروداکشن به دامنه‌های مجاز محدود شود
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API = settings.api_prefix
for r in (auth, sso, orgs, problems, applications, matching, collaborations,
          analytics, commercialization, maharat, misc, assistant):
    app.include_router(r.router, prefix=API)

# مهاجرت نسخه‌دار اسکیما (Alembic) — فقط در استقرار سرور؛ پرتیبل create_all خودش را دارد
# (در بستهٔ پرتیبل وابستگی alembic بسته نمی‌شود؛ import محافظت‌شده است)
try:
    from .migrations import run_upgrade_head  # noqa: E402
    _MIGRATION_NOTE = run_upgrade_head()
    if _MIGRATION_NOTE:
        print("[startup]", _MIGRATION_NOTE)
except ImportError:
    pass


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    request_id = uuid.uuid4().hex[:12]
    detail = exc.detail if isinstance(exc.detail, dict) else {
        "code": "error", "message": str(exc.detail)}
    detail["request_id"] = request_id
    return JSONResponse(status_code=exc.status_code, content=detail)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = uuid.uuid4().hex[:12]
    # پیام عمومی؛ جزئیات فقط در لاگ — جلوگیری از افشای اطلاعات حساس
    import traceback
    traceback.print_exc()
    return JSONResponse(status_code=500, content={
        "code": "internal_error",
        "message": "خطای داخلی سامانه؛ شناسه پیگیری خطا را به پشتیبانی بدهید",
        "request_id": request_id})


# ---------- Frontend (React build) ----------
DIST = settings.frontend_dist
if os.path.isdir(DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        # APIها بالاتر رجیستر شده‌اند؛ این مسیر فقط برای SPA است
        candidate = os.path.join(DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(DIST, "index.html"))
