"""ورود یکپارچه (SSO) — هم‌تراز با قرارداد اکوسیستم دانشجویار۳۶۰ + سخت‌سازی امنیتی v1.1.0.

طبق پنل مدیریت سامانه‌های دانشجویار۳۶۰ (همان الگوی برنامه‌یار۳۶۰/مهارت‌یار۳۶۰):
  سامانه: صنعت‌یار۳۶۰ | کلید سامانه (appKey): sanatyar | Client ID در SSO: sanatyar360
  «آدرس ورود» ثبت‌شده در مادر = نقطه شروع جریان OIDC این سامانه:
      GET /api/v1/auth/sso/login

قرارداد فرانت و مسیرها (یکسان با زیرسیستم‌های هم‌خانواده):
  GET  /api/v1/auth/sso/config          → {enabled, mode, login_url, label, redirect_uri_auto, …}
  GET  /api/v1/auth/sso/admin/config    → پیکربندی جاری (مدیر فنی)
  PUT  /api/v1/auth/sso/admin/config    → ذخیره پیکربندی زمان اجرا (issuer، client_id، …)
  GET  /api/v1/auth/sso/login           → شروع جریان (oidc → مادر | demo → شبیه‌ساز | disabled)
  GET  /api/v1/auth/sso/callback        → تبادل code (PKCE) → نشست با کوکی HttpOnly
  POST /api/v1/auth/sso/session         → تبادل امن کوکی نشست با توکن API (چرخش توکن)
  POST /api/v1/auth/sso/accept          → پذیرش توکن مرکز SSO سرویس‌به‌سرویس (HMAC مشترک)

سخت‌سازی v1.1.0 (فاز اعتماد):
  - توکن نشست دیگر در URL نمی‌آید؛ callback کوکی HttpOnly/SameSite=Lax ست می‌کند
    (Secure در HTTPS) و SPA با POST /session آن را به توکن API «چرخش‌یافته» تبدیل می‌کند.
  - جریان OIDC با PKCE (S256) و nonce؛ اعتبارسنجی issuer/audience ادعاهای id_token.
  - شبیه‌ساز فقط با SSO_ALLOW_SIMULATOR=1 فعال است؛ قطع پرتال در تولید مسیر جعلی نمی‌سازد.
  - نشست‌های محلی قابل ابطال‌اند (session_records + POST /auth/logout).
"""
import base64
import hashlib
import json
import os
import secrets
import time
import urllib.parse
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.deps import get_current_user, get_memberships
from ..core.security import (create_access_token, decode_token_payload,
                             register_session, revoke_session)
from ..db import get_db
from ..models import MemberRole, MembershipStatus, Organization, OrganizationMembership, User
from ..services import log_audit

router = APIRouter(prefix="/auth/sso", tags=["sso"])

# ذخیره موقت state → {ts, verifier, nonce} در حافظهٔ فرآیند — در پروداکشن به Redis منتقل شود
_state_store: dict[str, dict] = {}
_demo_codes: dict[str, dict] = {}

COOKIE_NAME = "uiis_session"

ROLE_MAP: dict[str, MemberRole] = {}
try:
    for k, v in json.loads(settings.sso_role_map).items():
        try:
            ROLE_MAP[k] = MemberRole(v)
        except ValueError:
            pass
except Exception:
    pass

DEMO_IDENTITIES = [
    {"email": "cio@nav.ac.ir", "name": "دکتر لیلا احمدی", "role": "sanatyar.admin",
     "label": "مدیر دفتر ارتباط با صنعت"},
    {"email": "rep@pastechno.ir", "name": "رضا محمدی", "role": "sanatyar.rep",
     "label": "نماینده صنعت — پارس‌تکنو"},
    {"email": "manager@pastechno.ir", "name": "سارا کریمی", "role": "sanatyar.manager",
     "label": "مدیر سازمان صنعتی"},
    {"email": "st2@nav.ac.ir", "name": "نگار صادقی", "role": "sanatyar.student",
     "label": "دانشجو — مهندسی کامپیوتر"},
    {"email": "prof.karimi@nav.ac.ir", "name": "دکتر حسن کریمی", "role": "sanatyar.professor",
     "label": "استاد — مهندسی کامپیوتر"},
    {"email": "expert@nav.ac.ir", "name": "دکتر فرهاد قاسمی", "role": "sanatyar.expert",
     "label": "کارشناس حوزه تخصصی"},
]

# ---------- پیکربندی زمان اجرا (فایل JSON — قابل ویرایش از پنل ادمین) ----------
# env همیشه اولویت دارد؛ فایل فقط مقدارهایی را نگه می‌دارد که ادمین ذخیره کرده است.
_RUNTIME_FIELDS = ["enabled", "issuer", "client_id", "scope", "default_role",
                   "auto_create", "redirect_uri", "redirect_web", "redirect_mobile", "label"]
_ENV_KEYS = {"issuer": "sso_issuer", "client_id": "sso_client_id", "scope": "sso_scope",
             "default_role": "sso_default_role", "label": "sso_label"}


def _load_runtime() -> dict:
    try:
        with open(settings.sso_runtime_config_path, encoding="utf-8") as f:
            data = json.load(f)
        return {k: data[k] for k in _RUNTIME_FIELDS if k in data}
    except Exception:
        return {}


def _save_runtime(patch: dict) -> dict:
    cur = _load_runtime()
    for k in _RUNTIME_FIELDS:
        if k in patch and patch[k] is not None:
            cur[k] = patch[k]
    try:
        os.makedirs(os.path.dirname(settings.sso_runtime_config_path) or ".", exist_ok=True)
        with open(settings.sso_runtime_config_path, "w", encoding="utf-8") as f:
            json.dump(cur, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
    return cur


def _cfg() -> dict:
    """پیکربندی مؤثر: env (settings) + فایل زمان اجرا (بدون override شدن توسط خالی)."""
    rt = _load_runtime()
    eff = {
        "enabled": rt.get("enabled", os.environ.get("SSO_ENABLED", "1") == "1"),
        "issuer": (getattr(settings, "sso_issuer") or "").rstrip("/") or rt.get("issuer", ""),
        "client_id": getattr(settings, "sso_client_id") or rt.get("client_id", "sanatyar360"),
        "scope": getattr(settings, "sso_scope") or rt.get("scope", "openid profile roles"),
        "default_role": getattr(settings, "sso_default_role") or rt.get("default_role", "student"),
        "auto_create": rt.get("auto_create", getattr(settings, "sso_auto_create", True)),
        "redirect_uri": rt.get("redirect_uri", ""),
        "redirect_web": rt.get("redirect_web", ""),
        "redirect_mobile": rt.get("redirect_mobile", ""),
        "label": getattr(settings, "sso_label") or rt.get("label", "ورود یکپارچه سازمانی"),
    }
    return eff


def sso_effective_mode() -> str:
    """oidc = مادر واقعی فعال؛ demo = شبیه‌ساز (فقط با SSO_ALLOW_SIMULATOR=1)؛ disabled."""
    c = _cfg()
    if c["enabled"] and c["issuer"]:
        return "oidc"
    if settings.sso_allow_simulator:
        return "demo"
    return "disabled"


def _pkce() -> tuple[str, str]:
    """تولید جفت PKCE (verifier، challenge=BASE64URL(SHA256(verifier))) — روش S256."""
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def _issuer_base(c: dict) -> str:
    return (c["issuer"] or "").rstrip("/")


def _endpoint(c: dict, kind: str) -> str:
    """نقطه پایانی OIDC: env اولویت دارد؛ در نبود آن از issuer مشتق می‌شود."""
    env_map = {"authorize": "sso_auth_url", "token": "sso_token_url", "userinfo": "sso_userinfo_url"}
    v = getattr(settings, env_map[kind])
    if v:
        return v
    return _issuer_base(c) + "/api/auth/sso/" + kind


def _base_url(request: Request) -> str:
    if settings.sso_public_base_url:
        return settings.sso_public_base_url.rstrip("/")
    return str(request.base_url).rstrip("/")


def _redirect_uri(request: Request, c: dict) -> str:
    return c["redirect_uri"] or _base_url(request) + "/api/v1/auth/sso/callback"


def _cleanup():
    now = time.time()
    for k in [k for k, v in _state_store.items() if now - (v.get("ts") or 0) > 600]:
        _state_store.pop(k, None)
    for k in [k for k, c in _demo_codes.items() if now - c.get("ts", 0) > 300]:
        _demo_codes.pop(k, None)


def _ensure_membership(db: Session, user: User, role: MemberRole):
    exists = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.role == role,
        OrganizationMembership.status == MembershipStatus.active).first()
    if exists:
        return
    # سازمان مقصد بر اساس نوع نقش
    want_university = role in (MemberRole.student, MemberRole.professor, MemberRole.cio_manager,
                               MemberRole.cio_expert, MemberRole.comm_expert,
                               MemberRole.university_admin, MemberRole.sys_admin)
    org = db.query(Organization).filter_by(org_type="university").first() if want_university \
        else db.query(Organization).filter_by(org_type="industry").first()
    if org:
        db.add(OrganizationMembership(user_id=user.id, organization_id=org.id,
                                      role=role, status=MembershipStatus.active))


def _provision(db: Session, email: str, name: str, master_roles: list[str]) -> User:
    c = _cfg()
    email = email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        if not c["auto_create"]:
            raise HTTPException(status_code=403, detail={
                "code": "sso_user_unknown",
                "message": "این حساب در صنعت‌یار۳۶۰ ثبت نشده است و ساخت خودکار خاموش است"})
        from ..core.security import hash_password
        import secrets as _secrets
        user = User(email=email, full_name=name or email, password_hash=hash_password(
            _secrets.token_hex(16)), user_type="staff", is_active=True)
        db.add(user)
        db.flush()
    mapped = None
    for r in master_roles:
        key = r.split(".")[-1] if "." in r else r
        if key in ROLE_MAP:
            mapped = ROLE_MAP[key]
            break
    default_role = ROLE_MAP.get(c["default_role"], MemberRole.student)
    _ensure_membership(db, user, mapped or default_role)
    return user


# ---------- قرارداد عمومی (مشترک با برنامه‌یار۳۶۰ و سایر زیرسیستم‌ها) ----------

@router.get("/config")
def sso_config(request: Request):
    c = _cfg()
    mode = sso_effective_mode()
    base = _base_url(request)
    providers = {"oidc": "دانشجو۳۶۰ (سامانه مادر)", "demo": "شبیه‌ساز داخلی دانشجو۳۶۰",
                 "disabled": "پیکربندی‌نشده"}
    return {
        "enabled": c["enabled"] and mode != "disabled",
        "mode": mode,
        "provider": providers[mode],
        "login_url": base + "/api/v1/auth/sso/login",
        "label": c["label"],
        "sub_label": "با حساب پرتال دانشجویار۳۶۰ — بدون تکرار رمز",
        "redirect_uri_auto": base + "/api/v1/auth/sso/callback",
        "session_method": "cookie",   # v1.1.0: نشست با کوکی HttpOnly — توکن در URL نیست
        "client_id": c["client_id"],
        "app_key": settings.sso_app_key,
        "issuer": _issuer_base(c),
        "note": "این مسیر (login_url) باید در پنل مدیریت سامانه‌های دانشجویار۳۶۰ به‌عنوان «آدرس ورود» ثبت شود",
    }


@router.get("/admin/config")
def sso_admin_config(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _require_sys_admin(user, db)
    c = _cfg()
    return {"config": c, "mode": sso_effective_mode(),
            "endpoints": {"authorize": _endpoint(c, "authorize"), "token": _endpoint(c, "token"),
                          "userinfo": _endpoint(c, "userinfo")},
            "app_key": settings.sso_app_key,
            "login_entry": "/api/v1/auth/sso/login",
            "shared_secret_set": bool(settings.sso_shared_secret)}


@router.put("/admin/config")
def sso_admin_update(payload: dict, request: Request, user: User = Depends(get_current_user),
                     db: Session = Depends(get_db)):
    _require_sys_admin(user, db)
    saved = _save_runtime({k: payload.get(k) for k in _RUNTIME_FIELDS if k in payload})
    return {"ok": True, "config": _cfg(), "mode": sso_effective_mode(),
            "login_url": _base_url(request) + "/api/v1/auth/sso/login",
            "hint": "اگر issuer و فعال‌سازی ست شده باشد، جریان OIDC با سامانه مادر اجرا می‌شود"}


def _require_sys_admin(user: User, db: Session):
    memberships = get_memberships(db, user)
    if not ({m.role for m in memberships} & {MemberRole.sys_admin}):
        raise HTTPException(status_code=403, detail={
            "code": "forbidden", "message": "تنظیم ورود یکپارچه فقط برای مدیر فنی سامانه"})


# ---------- جریان OIDC ----------

@router.get("/login")
def sso_login(request: Request):
    """نقطه ورود OIDC — همین مسیر در پنل سامانه مادر ثبت می‌شود."""
    _cleanup()
    mode = sso_effective_mode()
    if mode == "disabled":
        raise HTTPException(status_code=503, detail={
            "code": "sso_not_configured",
            "message": "ورود یکپارچه پیکربندی نشده است — issuer سامانه مادر را تنظیم کنید"})
    state = secrets.token_urlsafe(24)
    verifier, challenge = _pkce()
    nonce = secrets.token_urlsafe(16)
    _state_store[state] = {"ts": time.time(), "verifier": verifier, "nonce": nonce}
    c = _cfg()
    if mode == "oidc":
        params = {
            "client_id": c["client_id"],
            "response_type": "code",
            "scope": c["scope"],
            "redirect_uri": _redirect_uri(request, c),
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "app_key": settings.sso_app_key,
        }
        url = _endpoint(c, "authorize") + ("&" if "?" in _endpoint(c, "authorize") else "?") + \
            urllib.parse.urlencode(params)
        return RedirectResponse(url, status_code=302)
    # حالت نمایشی (فقط با SSO_ALLOW_SIMULATOR=1): صفحه شبیه‌ساز سامانه مادر
    return RedirectResponse("/#/sso-demo?state=" + urllib.parse.quote(state), status_code=302)


@router.post("/demo/authorize")
def demo_authorize(payload: dict, request: Request):
    """شبیه‌ساز سامانه مادر: صدور code پس از «احراز» در دانشجو۳۶۰."""
    state = payload.get("state", "")
    email = (payload.get("email") or "").lower().strip()
    if state not in _state_store:
        raise HTTPException(status_code=400, detail={"code": "invalid_state",
                                                     "message": "state نامعتبر یا منقضی است"})
    ident = next((i for i in DEMO_IDENTITIES if i["email"] == email), None)
    if not ident:
        raise HTTPException(status_code=404, detail={"code": "identity_not_found",
                                                     "message": "این حساب در شبیه‌ساز تعریف نشده است"})
    code = secrets.token_urlsafe(24)
    _demo_codes[code] = {"ts": time.time(), "email": ident["email"],
                         "name": ident["name"], "roles": [ident["role"]]}
    callback = _base_url(request) + "/api/v1/auth/sso/callback?code=" + \
        urllib.parse.quote(code) + "&state=" + urllib.parse.quote(state)
    return {"redirect": callback}


@router.get("/callback")
def sso_callback(request: Request, code: str = "", state: str = "", error: str = "",
                 db: Session = Depends(get_db)):
    """پایان جریان: تبادل code با مادر (PKCE) → اعتبارسنجی ادعاها → نشست با کوکی HttpOnly.

    توکن نشست در URL نمی‌آید؛ مرورگر با کوکی HttpOnly به /session می‌رود و توکن API
    چرخش‌یافته را می‌گیرد. این امر افشای توکن در تاریخچه/لاگ/ارجاع را حذف می‌کند.
    """
    _cleanup()
    if error:
        return RedirectResponse("/?sso_error=" + urllib.parse.quote(error), status_code=302)
    entry_state = _state_store.get(state or "")
    if not state or not entry_state:
        return RedirectResponse("/?sso_error=" + urllib.parse.quote("invalid_state"), status_code=302)
    _state_store.pop(state, None)
    c = _cfg()
    mode = sso_effective_mode()

    if mode == "oidc":
        # تبادل code با نقطه پایان Token سامانه مادر + code_verifier (PKCE)
        data = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _redirect_uri(request, c),
            "client_id": c["client_id"],
            "client_secret": settings.sso_client_secret,
            "code_verifier": entry_state.get("verifier", ""),
        }).encode()
        req = urllib.request.Request(_endpoint(c, "token"), data=data, method="POST",
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                token_res = json.loads(res.read().decode())
        except Exception:
            return RedirectResponse("/?sso_error=" + urllib.parse.quote("provider_error"), status_code=302)
        claims: dict = {}
        if token_res.get("id_token"):
            claims = decode_token_payload(token_res["id_token"]) or {}
            # اعتبارسنجی دقیق id_token: issuer، audience و nonce
            if claims.get("iss") and claims["iss"].rstrip("/") != _issuer_base(c):
                return RedirectResponse("/?sso_error=" + urllib.parse.quote("issuer_mismatch"), status_code=302)
            aud = claims.get("aud")
            aud_list = aud if isinstance(aud, list) else [aud]
            if aud and c["client_id"] not in aud_list:
                return RedirectResponse("/?sso_error=" + urllib.parse.quote("audience_mismatch"), status_code=302)
            if claims.get("nonce") and claims["nonce"] != entry_state.get("nonce"):
                return RedirectResponse("/?sso_error=" + urllib.parse.quote("nonce_mismatch"), status_code=302)
        if settings.sso_userinfo_url and token_res.get("access_token"):
            ureq = urllib.request.Request(_endpoint(c, "userinfo"),
                                          headers={"Authorization": "Bearer " + token_res["access_token"]})
            try:
                with urllib.request.urlopen(ureq, timeout=15) as res:
                    claims.update(json.loads(res.read().decode()))
            except Exception:
                pass
        email = claims.get("email") or ""
        name = claims.get("name") or claims.get("full_name") or email
        master_roles = claims.get("roles") or []
        if isinstance(master_roles, str):
            master_roles = master_roles.split()
    else:
        entry = _demo_codes.pop(code, None)
        if not entry:
            return RedirectResponse("/?sso_error=" + urllib.parse.quote("invalid_code"), status_code=302)
        email, name, master_roles = entry["email"], entry["name"], entry["roles"]

    if not email:
        return RedirectResponse("/?sso_error=" + urllib.parse.quote("no_email"), status_code=302)
    user = _provision(db, email, name, master_roles)
    log_audit(db, user.id, "sso_login", "user", user.id,
              {"mode": mode, "master_roles": master_roles}, request)
    db.commit()
    token = create_access_token(user.id)
    register_session(db, token, user.id)
    db.commit()
    resp = RedirectResponse("/?sso_login=1", status_code=302)
    resp.set_cookie(COOKIE_NAME, token, max_age=settings.jwt_expire_minutes * 60,
                    httponly=True, samesite="lax",
                    secure=request.url.scheme == "https", path="/")
    return resp


@router.post("/session")
def sso_session(request: Request, db: Session = Depends(get_db)):
    """تبادل امن کوکی نشست با توکن API (چرخش توکن) — خروجی همان شکل /auth/login."""
    cookie_token = request.cookies.get(COOKIE_NAME, "")
    if not cookie_token:
        raise HTTPException(status_code=401, detail={
            "code": "no_sso_session",
            "message": "نشست ورود یکپارچه یافت نشد — از دکمه ورود یکپارچه شروع کنید"})
    from ..core.security import is_session_revoked
    claims = decode_token_payload(cookie_token) or {}
    user_id = claims.get("sub")
    if not user_id or is_session_revoked(db, claims.get("jti")):
        raise HTTPException(status_code=401, detail={
            "code": "invalid_sso_session",
            "message": "نشست ورود یکپارچه نامعتبر یا باطل شده است"})
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail={
            "code": "inactive", "message": "کاربر غیرفعال است"})
    # چرخش: نشست کوکی ابطال و توکن تازه صادر می‌شود
    revoke_session(db, claims.get("jti"))
    token = create_access_token(user.id)
    register_session(db, token, user.id)
    log_audit(db, user.id, "sso_session_exchange", "user", user.id, {}, request)
    db.commit()
    from .auth import _me_payload
    return {"access_token": token, "token_type": "bearer", "mode": "sso_cookie",
            **_me_payload(db, user)}


@router.post("/accept")
def sso_accept(payload: dict, request: Request, db: Session = Depends(get_db)):
    """مدل سبک ورود یکپارچه (?sso_token= در URL): پذیرش توکن صادرشده مرکز SSO/مادر.

    توکن JWT با کلید مشترک (SSO_SHARED_SECRET) امضا شده باشد؛ ادعاهای مورد انتظار:
      email (الزامی)، name/full_name، roles (فهرست نقش‌های مادر مثل sanatyar.student)
    خروجی همان شکل /auth/login است تا SPA بدون تغییر نشست را بسازد.
    """
    token = (payload.get("token") or "").strip()
    if not token or not settings.sso_shared_secret:
        raise HTTPException(status_code=400, detail={
            "code": "sso_accept_unavailable",
            "message": "پذیرش توکن یکپارچه فعال نیست (کلید مشترک SSO تنظیم نشده است)"})
    from ..core.security import verify_hmac_token
    claims = verify_hmac_token(token, settings.sso_shared_secret)
    if not claims:
        raise HTTPException(status_code=401, detail={
            "code": "invalid_sso_token",
            "message": "توکن ورود یکپارچه نامعتبر یا منقضی است"})
    email = (claims.get("email") or "").lower().strip()
    if not email:
        raise HTTPException(status_code=422, detail={
            "code": "no_email", "message": "توکن مرکز SSO فیلد email ندارد"})
    name = claims.get("name") or claims.get("full_name") or email
    roles = claims.get("roles") or ["sanatyar." + (_cfg()["default_role"] or "student")]
    if isinstance(roles, str):
        roles = roles.split()
    user = _provision(db, email, name, roles)
    log_audit(db, user.id, "sso_accept_login", "user", user.id,
              {"master_roles": roles}, request)
    db.commit()
    from .auth import _me_payload
    return {"access_token": create_access_token(user.id), "token_type": "bearer",
            "mode": "sso_accept", **_me_payload(db, user)}


@router.get("/demo/identities")
def demo_identities():
    return {"items": DEMO_IDENTITIES, "mode": sso_effective_mode()}
