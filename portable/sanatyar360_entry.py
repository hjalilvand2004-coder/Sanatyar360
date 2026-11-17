"""نقطه ورود نسخه پرتیبل صنعت‌یار۳۶۰ — بدون نیاز به پایتون/پستگرس روی مقصد.

اجرا: sanatyar360.exe (ویندوز) یا ./sanatyar360 (لینوکس)
- پایگاه داده: فایل SQLite کنار برنامه (sanatyar360.db)
- رابط وب: به‌صورت خودکار در مرورگر باز می‌شود (با --no-browser خاموش کنید)
- گزینه‌ها: --port 8092 --host 127.0.0.1 --no-browser --reset-db
"""
import os
import sys
import threading
import time

# --- تنظیم محیط قبل از بارگذاری اپ ---
if getattr(sys, "frozen", False):
    os.environ.setdefault("UIIS_PORTABLE", "1")
    DATA_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    DATA_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(DATA_DIR, "sanatyar360.db")
os.environ.setdefault("DATABASE_URL", "sqlite:///" + DB_PATH.replace("\\", "/"))

HOST, PORT, OPEN_BROWSER = "127.0.0.1", 8092, True
if "--reset-db" in sys.argv and os.path.exists(DB_PATH):
    os.remove(DB_PATH)
for i, a in enumerate(sys.argv):
    if a == "--port" and i + 1 < len(sys.argv):
        PORT = int(sys.argv[i + 1])
    if a == "--host" and i + 1 < len(sys.argv):
        HOST = sys.argv[i + 1]
    if a == "--no-browser":
        OPEN_BROWSER = False


def main():
    # مهم: ابتدا مدل‌ها باید import شوند تا metadata کامل باشد، بعد create_all
    from app import models  # noqa: F401
    from app.db import Base, engine
    Base.metadata.create_all(engine)

    from app.db import SessionLocal
    from app.models import User
    db = SessionLocal()
    empty = db.query(User).count() == 0
    db.close()
    if empty:
        print("داده نمونه اولیه ساخته می‌شود…")
        import seed
        seed.main()

    url = f"http://{'localhost' if HOST == '127.0.0.1' else HOST}:{PORT}"
    if OPEN_BROWSER:
        def _open():
            time.sleep(1.5)
            try:
                import webbrowser
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()

    print(f"\n  صنعت‌یار۳۶۰ (نسخه پرتیبل) روی {url} اجرا شد — برای خروج Ctrl+C\n")
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
