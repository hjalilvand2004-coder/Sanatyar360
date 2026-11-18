# سامانه تعامل دانشگاه و صنعت — دانشجو۳۶۰

بستر مدیریت چرخه: **ثبت مسئله صنعتی ← بررسی و انتشار ← شناسایی ظرفیت علمی ← پیشنهاد و درخواست همکاری ← تشکیل تیم و توافق ← پیگیری همکاری ← ثبت دستاورد و تحلیل اثر**

مبتنی بر: **FastAPI + React + TypeScript + PostgreSQL 16** (مونولیت ماژولار مطابق سند نیازمندی‌ها، بخش ۴)

---

## ۱) اجزای سامانه

| مسیر | توضیح |
|---|---|
| `backend/` | API کامل FastAPI (ماژول‌های auth، organizations، problems، applications، matching، collaborations، analytics، commercialization، misc) |
| `backend/app/models.py` | مدل داده (~۳۰ جدول مطابق بخش ۵ سند) |
| `backend/seed.py` | داده نمونه: ۱۴ کاربر، ۳ سازمان، ۴ مسئله، درخواست‌ها، پروژه همکاری فعال، داده بازار، پرونده تجاری‌سازی |
| `frontend/` | رابط کاربری React + TypeScript — فارسی، راست‌به‌چپ، فونت وزیرمتن، تاریخ شمسی |
| `deploy/` | Docker Compose، Dockerfileها، nginx و راهنمای همین فایل |
| `docs/api.md` | فهرست APIهای اصلی |

**مستندات تعاملی API:** بعد از استقرار در آدرس `/api/docs` (Swagger UI).

## ۲) استقرار روی سرور 188.212.96.235 — پورت 8092

### گزینه A — Docker (پیشنهادی، سریع‌ترین راه)

```bash
# 1) انتقال بسته به سرور
scp uiis-deploy.tar.gz root@188.212.96.235:/opt/uiis.tar.gz
ssh root@188.212.96.235 "mkdir -p /opt/uiis && tar xzf /opt/uiis.tar.gz -C /opt/uiis"

# 2) تنظیم رمزها
cd /opt/uiis/deploy
cp .env.example .env
nano .env    # POSTGRES_PASSWORD و JWT_SECRET را حتماً عوض کنید

# 3) اجرا
docker compose up -d --build
# داده نمونه در اولین اجرا خودکار ساخته می‌شود
```

سامانه روی `http://188.212.96.235:8092` در دسترس است.
برای از نو ساختن داده نمونه: `docker compose exec api python seed.py --reset`

### گزینه B — بدون Docker

```bash
apt install -y python3-venv nodejs npm postgresql
sudo -u postgres psql -c "CREATE USER uiis PASSWORD 'STRONG_PASS'; CREATE DATABASE uiis OWNER uiis;"

cd backend && python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL="postgresql+psycopg://uiis:STRONG_PASS@127.0.0.1:5432/uiis"
python seed.py
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8092 &

cd ../frontend && npm install && npx vite build
# سپس فایل‌های dist را با nginx یا همان uvicorn سرو کنید
# (uvicorn به‌صورت پیش‌فرض dist را سرو می‌کند اگر FRONTEND_DIST تنظیم باشد)
```

برای اجرای پایدار، سرویس systemd بسازید یا nginx را جلوی uvicorn قرار دهید.

## ۳) حساب‌های نمونه (رمز همه: `uiis1234`)

| ایمیل | نقش |
|---|---|
| cio@nav.ac.ir | مدیر دفتر ارتباط با صنعت |
| expert@nav.ac.ir | کارشناس حوزه تخصصی (داور مسئله) |
| rep@pastechno.ir | نماینده صنعت — پارس‌تکنو (مسئله ثبت و منتشر می‌کند) |
| manager@pastechno.ir | مدیر سازمان صنعتی |
| st1 / st2 / st3 @nav.ac.ir | دانشجویان |
| prof.hosseini / prof.karimi @nav.ac.ir | استادان |
| comm@nav.ac.ir | کارشناس تجاری‌سازی |
| uniadmin@nav.ac.ir | مدیر دانشگاه |
| sysadmin@uiis-system.ir | مدیر فنی (حسابرسی عملیات) |

## ۴) چک‌لیست پس از استقرار

- [ ] `curl http://188.212.96.235:8092/api/v1/health` → `{"status":"ok"}`
- [ ] ورود با حساب cio و مشاهده داشبورد
- [ ] تغییر `JWT_SECRET` و `POSTGRES_PASSWORD` در `.env`
- [ ] فعال‌سازی HTTPS (مثلاً با nginx + certbot جلوی پورت 8092) — طبق بخش ۹ سند الزامی است
- [ ] تست پشتیبان‌گیری: `bash deploy/backup_restore_test.sh` (AC-14)
- [ ] در صورت اتصال به هویت یکپارچه دانشجو۳۶۰، OIDC در `backend/app/core/security.py` جایگزین شود

## ۵) پشتیبان‌گیری و بازیابی (AC-14)

```bash
# پشتیبان‌گیری دوره‌ای
docker compose exec db pg_dump -U uiis uiis > backup_$(date +%F).sql

# تست بازیابی واقعی (روی دیتابیس موازی)
bash deploy/backup_restore_test.sh
```

## ۶) نقشه توسعه بعدی (مطابق سند)

- فاز ۲: تطبیق معنایی با pgvector، دریافت دوره‌ای داده بازار از منابع مجاز
- فاز ۳: تحلیل شبکه پیشرفته، گردش‌کار کامل تجاری‌سازی
- پیش از اجرای عملی: موارد بخش ۱۴ سند (تصمیم‌های ضروری) تعیین تکلیف شوند

## ۷) ملاحظات امنیتی MVP

- این نسخه برای نمایش MVP است؛ در پروداکشن: رمزها و Secretها از `.env` مدیریت شوند، CORS محدود شود، HTTPS فعال شود، احراز دومرحله‌ای برای نقش‌های حساس اضافه شود و فایل‌ها روی Object Storage مستقر شوند.
- فایل‌های بارگذاری‌شده خارج از مسیر عمومی وب و با URL موقت سرو می‌شوند؛ لیست پسوند مجاز و سقف ۲۰MB اعمال شده است.
- عملیات حساس در `audit_logs` با عامل، زمان، موضوع و IP ثبت می‌شود.
