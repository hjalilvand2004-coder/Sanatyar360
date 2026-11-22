import os
import sys

from pydantic_settings import BaseSettings

APP_TITLE = "صنعت‌یار۳۶۰ — اتصال دانشجو به صنعت | زیرسیستم دانشجو۳۶۰"

# --- تشخیص حالت پرتیبل (exe بدون پایتون روی مقصد) ---
FROZEN = bool(getattr(sys, "frozen", False)) or os.environ.get("UIIS_PORTABLE") == "1"


def _portable_data_dir() -> str:
    # کنار فایل اجرایی — در حالت onefile، sys.executable در پوشه واقعی است
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


if FROZEN:
    _DATA = _portable_data_dir()
    _DEFAULT_DB = "sqlite:///" + os.path.join(_DATA, "sanatyar360.db").replace("\\", "/")
    _DEFAULT_UPLOADS = os.path.join(_DATA, "uploads")
    _DEFAULT_FRONTEND_DIST = os.path.join(getattr(sys, "_MEIPASS", _DATA), "webdist")
else:
    _DEFAULT_DB = "postgresql+psycopg://postgres@127.0.0.1:5432/uiis"
    _DEFAULT_UPLOADS = "/home/z/my-project/uiis/uploads"
    _DEFAULT_FRONTEND_DIST = "/home/z/my-project/uiis/frontend/dist"


def _default_jwt_secret() -> str:
    # در حالت پرتیبل، Secret تصادفی یک‌بار ساخته و کنار برنامه ذخیره می‌شود
    env = os.environ.get("JWT_SECRET")
    if env:
        return env
    if FROZEN:
        try:
            keyfile = os.path.join(_portable_data_dir(), ".jwt_secret")
            if os.path.exists(keyfile):
                return open(keyfile, encoding="utf-8").read().strip()
            import secrets
            token = secrets.token_hex(32)
            with open(keyfile, "w", encoding="utf-8") as f:
                f.write(token)
            return token
        except OSError:
            return "portable-fallback-secret"
    return "uiis-demo-secret-change-in-production"


class Settings(BaseSettings):
    app_name: str = APP_TITLE
    api_prefix: str = "/api/v1"

    # PostgreSQL در استقرار سرور؛ SQLite در حالت پرتیبل (override با DATABASE_URL)
    database_url: str = os.environ.get("DATABASE_URL", _DEFAULT_DB)

    jwt_secret: str = _default_jwt_secret()
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    uploads_dir: str = os.environ.get("UPLOADS_DIR", _DEFAULT_UPLOADS)
    frontend_dist: str = os.environ.get("FRONTEND_DIST", _DEFAULT_FRONTEND_DIST)
    max_upload_mb: int = 20

    # AI governance: master switch to fall back to rule-based baseline
    ai_enabled: bool = True

    # ---------- ورود یکپارچه (SSO/OIDC) با سامانه مادر دانشجو۳۶۰ ----------
    # طبق پنل مدیریت سامانه‌های دانشجو۳۶۰ (مانند برنامه‌یار۳۶۰ و مهارت‌یار۳۶۰):
    #   کلید سامانه (appKey): sanatyar | Client ID: sanatyar360
    #   آدرس ورود سامانه = نقطه شروع جریان OIDC همین سامانه: /api/v1/auth/sso/login
    #   issuer = نشانی پرتال سازمانی (سامانه مادر) — نقاط پایانی از آن مشتق می‌شود
    sso_app_key: str = os.environ.get("SSO_APP_KEY", "sanatyar")
    sso_client_id: str = os.environ.get("SSO_CLIENT_ID", "sanatyar360")
    sso_client_secret: str = os.environ.get("SSO_CLIENT_SECRET", "")
    sso_issuer: str = os.environ.get("SSO_ISSUER", "")          # مثال: http://188.212.96.235:8086
    sso_auth_url: str = os.environ.get("SSO_AUTH_URL", "")      # پیش‌فرض: {issuer}/api/auth/sso/authorize
    sso_token_url: str = os.environ.get("SSO_TOKEN_URL", "")    # پیش‌فرض: {issuer}/api/auth/sso/token
    sso_userinfo_url: str = os.environ.get("SSO_USERINFO_URL", "")  # پیش‌فرض: {issuer}/api/auth/sso/userinfo
    sso_scope: str = os.environ.get("SSO_SCOPE", "openid profile roles")
    sso_default_role: str = os.environ.get("SSO_DEFAULT_ROLE", "student")
    sso_auto_create: bool = os.environ.get("SSO_AUTO_CREATE", "1") == "1"
    sso_label: str = os.environ.get("SSO_LABEL", "ورود یکپارچه سازمانی")
    # توکن مشترک با مرکز SSO (مدل سبک sso_token) — کلید HMAC برای اعتبارسنجی توکن مادر
    sso_shared_secret: str = os.environ.get("SSO_SHARED_SECRET", "")
    # شبیه‌ساز ورود فقط با تنظیم صریح محیط توسعه/دمو فعال می‌شود (پرتیبل خودش ست می‌کند)
    sso_allow_simulator: bool = os.environ.get("SSO_ALLOW_SIMULATOR", "0") == "1"
    sso_public_base_url: str = os.environ.get("SSO_PUBLIC_BASE_URL", "")  # اگر پشت پروکسی است
    # پیکربندی زمان اجرا (پنل ادمین) — فایل JSON کنار داده‌ها؛ env همچنان اولویت دارد
    sso_runtime_config_path: str = os.environ.get(
        "SSO_RUNTIME_CONFIG_PATH",
        os.path.join(_portable_data_dir() if FROZEN else os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                     "sso_config.json"),
    )
    # نگاشت نقش‌های سامانه مادر (مثل sanatyar.admin) به نقش‌های محلی
    sso_role_map: str = os.environ.get(
        "SSO_ROLE_MAP",
        '{"admin": "cio_manager", "manager": "industry_manager", "rep": "industry_rep", '
        '"student": "student", "professor": "professor", "expert": "cio_expert", '
        '"comm": "comm_expert", "viewer": "student"}',
    )

    # ---------- زیرسیستم مهارتیار۳۶۰ (پروفایل مهارتی تأییدشده دانشجو) ----------
    # ارتباط تنگاتنگ در اکوسیستم دانشجویار۳۶۰: واژه‌نامه مهارت، پروفایل تأییدشده،
    # شکاف مهارتی و تقویت موتور تطبیق با شواهد معتبر مهارتیار.
    maharat_api_url: str = os.environ.get("MAHARAT_API_URL", "http://188.212.96.235:8090/api/v1")
    maharat_enabled: bool = os.environ.get("MAHARAT_ENABLED", "1") == "1"
    maharat_service_email: str = os.environ.get("MAHARAT_SERVICE_EMAIL", "admin@demo.local")
    maharat_service_password: str = os.environ.get("MAHARAT_SERVICE_PASSWORD", "Maharat#360")
    maharat_timeout: int = int(os.environ.get("MAHARAT_TIMEOUT", "6"))


settings = Settings()


def sso_mode() -> str:
    """oidc = سامانه مادر واقعی؛ demo = شبیه‌ساز داخلی برای تست بدون سامانه مادر."""
    return "oidc" if settings.sso_auth_url else "demo"
