# نسخه پرتیبل صنعت‌یار۳۶۰ — راهنمای اجرا

این نسخه **هیچ نیازی به نصب پایتون، PyCharm یا PostgreSQL** ندارد.
همه‌چیز داخل یک فایل اجرایی واحد بسته شده است (FastAPI + رابط وب + پایگاه داده SQLite + داده نمونه).

## اجرا

1. فایل `Sanatyar360.exe` (ویندوز) یا `Sanatyar360` (لینوکس) را در یک پوشه قرار دهید.
2. روی آن دوبار کلیک کنید (لینوکس: `./Sanatyar360`).
3. مرورگر به‌صورت خودکار روی `http://localhost:8092` باز می‌شود.

فایل‌هایی که کنار برنامه ساخته می‌شوند:

| فایل | کاربرد |
|---|---|
| `sanatyar360.db` | پایگاه داده SQLite (داده شما — برای انتقال کافی است همین فایل را کپی کنید) |
| `.jwt_secret` | کلید امضای توکن (به‌صورت خودکار یک‌بار ساخته می‌شود) |
| `uploads/` | پیوست‌ها |

## گزینه‌های خط فرمان

```
Sanatyar360.exe --port 8092          # پورت (پیش‌فرض 8092)
Sanatyar360.exe --host 0.0.0.0       # دسترسی از دیگر رایانه‌های شبکه
Sanatyar360.exe --no-browser         # باز نکردن مرورگر
Sanatyar360.exe --reset-db           # بازنشانی به داده نمونه اولیه
```

## ورود به سامانه

- **ورود یکپارچه (SSO)**: دکمه نارنجی «ورود یکپارچه با حساب دانشجو۳۶۰» — جریان کامل OIDC با Client ID `sanatyar360` و کلید سامانه `sanatyar`.
  - در نسخه پرتیبل، چون سامانه مادر در دسترس نیست، **شبیه‌ساز داخلی** با همان جریان اجرا می‌شود.
  - در استقرار واقعی این متغیرها را قبل از اجرا ست کنید:
    ```
    set SSO_AUTH_URL=http://188.212.96.235:8086/oidc/auth
    set SSO_TOKEN_URL=http://188.212.96.235:8086/oidc/token
    set SSO_CLIENT_ID=sanatyar360
    set SSO_CLIENT_SECRET=...
    set SSO_PUBLIC_BASE_URL=http://188.212.96.235:8092
    ```
  - و آدرس `http://188.212.96.235:8092/api/v1/auth/sso/login` را در پنل «مدیریت سامانه‌ها»ی دانشجو۳۶۰ به‌عنوان **آدرس ورود** ثبت کنید.
  - نقش‌های مادر مثل `sanatyar.admin` / `sanatyar.rep` / `sanatyar.student` با `SSO_ROLE_MAP` به نقش‌های سامانه نگاشت می‌شوند.
- **ورود محلی**: حساب‌های نمونه با رمز `uiis1234` (مثلاً `cio@nav.ac.ir`).

## نحوه ساخت نسخه پرتیبل (برای توسعه‌دهندگان)

```bash
cd frontend && npm install && npx vite build
pip install -r portable/requirements-portable.txt
pyinstaller portable/sanatyar360.spec --distpath dist_portable
```

خروجی: `dist_portable/sanatyar360(.exe)` — فایل اجرایی مستقل (~۵۶MB).
ساخت خودکار ویندوز/لینوکس با GitHub Actions در پوشه `.github/workflows/` انجام می‌شود؛
بعد از push یک تگ مثل `v1.0.0`، فایل‌های آماده دانلود در GitHub Release قرار می‌گیرد.
