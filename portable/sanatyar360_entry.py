"""نقطه ورود نسخه پرتیبل صنعت‌یار۳۶۰ — بدون نیاز به پایتون/پستگرس روی مقصد.

اجرا: Sanatyar360.exe (ویندوز) یا ./Sanatyar360 (لینوکس)
- پایگاه داده: فایل SQLite کنار برنامه (sanatyar360.db)
- رابط وب: پس از آماده‌شدن سرور، مرورگر خودکار باز می‌شود (با --no-browser خاموش کنید)
- گزینه‌ها: --port 8092 --host 127.0.0.1 --no-browser --reset-db
- ثبت رویدادها: فایل sanatyar360.log کنار برنامه — در بروز خطا حتماً این فایل را ببینید
"""
import os
import socket
import sys
import time
import traceback

FROZEN = bool(getattr(sys, "frozen", False)) or os.environ.get("UIIS_PORTABLE") == "1"

# دایرکتوری داده: کنار فایل اجرایی (در onefile هم sys.executable مسیر واقعی است)
BASE_DIR = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) \
    else os.path.dirname(os.path.abspath(__file__))
try:
    os.chdir(BASE_DIR)
except OSError:
    pass

LOG_PATH = os.path.join(BASE_DIR, "sanatyar360.log")
DB_PATH = os.path.join(BASE_DIR, "sanatyar360.db")


def log(msg: str):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def parse_args(argv: list[str]):
    host, port, open_browser = "127.0.0.1", 8092, True
    reset_db = False
    for i, a in enumerate(argv):
        if a == "--port" and i + 1 < len(argv):
            try:
                port = int(argv[i + 1])
            except ValueError:
                pass
        elif a == "--host" and i + 1 < len(argv):
            host = argv[i + 1]
        elif a == "--no-browser":
            open_browser = False
        elif a == "--reset-db":
            reset_db = True
    return host, port, open_browser, reset_db


def find_free_port(start: int, tries: int = 8) -> int:
    """اگر پورت خواسته‌شده اشغال بود، اولین پورت آزاد بعدی را برمی‌گرداند."""
    for p in range(start, start + tries):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.bind(("127.0.0.1", p))
            return p
        except OSError:
            continue
        finally:
            try:
                s.close()
            except OSError:
                pass
    return start  # همان پورت — خطای واضح در لاگ ثبت می‌شود


def wait_until_listening(host: str, port: int, timeout_s: int = 60) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        try:
            s.connect((host if host != "0.0.0.0" else "127.0.0.1", port))
            return True
        except OSError:
            time.sleep(0.5)
        finally:
            s.close()
    return False


def parse_url_hostport(url: str):
    # url مثل http://localhost:8092
    rest = url.split("//", 1)[-1]
    host, _, port = rest.partition(":")
    return host, int(port or 80)


def open_browser_when_ready(url: str):
    """مرورگر فقط پس از پاسخ‌گوی شدن سرور باز می‌شود (نه قبل از آن)."""
    if wait_until_listening(*parse_url_hostport(url), timeout_s=90):
        try:
            import webbrowser
            webbrowser.open(url)
            log(f"مرورگر باز شد: {url}")
        except Exception as e:
            log(f"باز شدن خودکار مرورگر ناموفق بود — دستی باز کنید: {url} ({e})")
    else:
        log(f"سرور پس از 90 ثانیه پاسخ نداد — مرورگر باز نشد؛ لاگ را بررسی کنید: {url}")


def run(host: str, port: int, open_browser: bool, reset_db: bool):
    log(f"صنعت‌یار۳۶۰ — نسخه پرتیبل | دایرکتوری: {BASE_DIR}")

    if reset_db and os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        log("پایگاه داده قبلی حذف شد (--reset-db)")

    # --- محیط قبل از بارگذاری اپ ---
    os.environ.setdefault("UIIS_PORTABLE", "1")
    os.environ.setdefault(
        "DATABASE_URL", "sqlite:///" + DB_PATH.replace("\\", "/"))

    # 1) مدل‌ها ابتدا import شوند تا metadata کامل باشد، بعد create_all
    log("۱/۴ بارگذاری ماژول‌ها…")
    from app import models  # noqa: F401
    from app.db import Base, engine, SessionLocal
    Base.metadata.create_all(engine)

    # 2) داده نمونه فقط بار اول
    log("۲/۴ بررسی پایگاه داده…")
    from app.models import User
    db = SessionLocal()
    empty = db.query(User).count() == 0
    db.close()
    if empty:
        log("۳/۴ ساخت داده نمونه اولیه (حدود ۱۰ تا ۳۰ ثانیه)…")
        import seed
        seed.main()
        log("۳/۴ داده نمونه ساخته شد.")
    else:
        log("۳/۴ پایگاه داده موجود استفاده می‌شود.")

    # 4) اجرای سرور با آبجکت اپ (بدون import رشته‌ای — سازگار با فریز ویندوز)
    from app.main import app
    import uvicorn
    url = f"http://{'localhost' if host == '127.0.0.1' else host}:{port}"
    log(f"۴/۴ شروع وب‌سرور روی {url} — برای خروج پنجره را ببندید یا Ctrl+C بزنید")
    if open_browser:
        import threading
        threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")


def main():
    host, port, open_browser, reset_db = parse_args(sys.argv[1:])
    port = find_free_port(port)
    try:
        run(host, port, open_browser, reset_db)
    except KeyboardInterrupt:
        log("برنامه توسط کاربر متوقف شد.")
    except SystemExit:
        raise
    except BaseException:
        err = traceback.format_exc()
        log("خطا در اجرا:\n" + err)
        print("\n" + "=" * 60)
        print("برنامه با خطا متوقف شد.")
        print(f"جزئیات در فایل زیر ثبت شد:\n  {LOG_PATH}")
        print("اگر این خطا تکرار شد، محتوای فایل لاگ را برای پشتیبانی بفرستید.")
        print("=" * 60 + "\n")
        if FROZEN and sys.stdin is not None and sys.stdin.isatty():
            try:
                input("برای بستن این پنجره Enter بزنید…")
            except EOFError:
                pass
        sys.exit(1)


if __name__ == "__main__":
    main()
