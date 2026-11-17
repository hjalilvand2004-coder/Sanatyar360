"""ورود یکپارچه (SSO) — جریان OIDC با سامانه مادر دانشجو۳۶۰.

طبق پنل مدیریت سامانه‌های دانشجو۳۶۰:
  سامانه: صنعت‌یار۳۶۰ | کلید سامانه (appKey): sanatyar | Client ID: sanatyar360
  «آدرس ورود» سامانه باید نقطه شروع جریان OIDC سامانه مقصد باشد ← همین مسیر:
  GET /api/v1/auth/sso/login

دو حالت:
  - oidc: وقتی SSO_AUTH_URL تنظیم شده باشد، ریدایرکت واقعی به سامانه مادر انجام می‌شود.
  - demo : در نبود سامانه مادر، شبیه‌ساز داخلی با همان شکل و جریان اجرا می‌شود
           (برای تست پرتیبل؛ در محیط عملیاتی با متغیرهای SSO_* حذف می‌شود).
"""
import json
import secrets
import time
import urllib.parse
import urllib.request

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..core.config import settings, sso_mode
from ..core.security import create_access_token
from ..db import get_db
from ..models import (
    MemberRole, MembershipStatus, Organization, OrganizationMembership, User,
)
from ..services import log_audit

router = APIRouter(prefix="/auth/sso", tags=["sso"])

# ذخیره موقت state/code در حافظهٔ فرآیند — در پروداکشن به Redis/دیتابیس منتقل شود
_state_store: dict[str, float] = {}
_demo_codes: dict[str, dict] = {}

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


def _base_url(request: Request) -> str:
    return settings.sso_public_base_url.rstrip("/") or str(request.base_url).rstrip("/")


def _cleanup():
    now = time.time()
    for k in [k for k, t in _state_store.items() if now - t > 600]:
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
    email = email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user:
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
    _ensure_membership(db, user, mapped or MemberRole.student)
    return user


@router.get("/config")
def sso_config():
    return {
        "mode": sso_mode(),
        "provider": "دانشجو۳۶۰ (سامانه مادر)" if sso_mode() == "oidc" else "شبیه‌ساز داخلی دانشجو۳۶۰",
        "client_id": settings.sso_client_id,
        "app_key": settings.sso_app_key,
        "entry_url": "/api/v1/auth/sso/login",
        "note": "در استقرار واقعی، این مسیر در پنل مدیریت سامانه‌های دانشجو۳۶۰ به‌عنوان «آدرس ورود» ثبت می‌شود",
    }


@router.get("/login")
def sso_login(request: Request):
    """نقطه ورود OIDC — همین مسیر در پنل سامانه مادر ثبت می‌شود."""
    _cleanup()
    state = secrets.token_urlsafe(24)
    _state_store[state] = time.time()
    if sso_mode() == "oidc":
        params = {
            "client_id": settings.sso_client_id,
            "response_type": "code",
            "scope": "openid profile roles",
            "redirect_uri": _base_url(request) + "/api/v1/auth/sso/callback",
            "state": state,
        }
        url = settings.sso_auth_url + ("&" if "?" in settings.sso_auth_url else "?") + \
            urllib.parse.urlencode(params)
        return RedirectResponse(url, status_code=302)
    # حالت نمایشی: صفحه شبیه‌ساز سامانه مادر (همان جریان، همان callback)
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
def sso_callback(request: Request, code: str = "", state: str = "",
                 db: Session = Depends(get_db)):
    _cleanup()
    if not state or state not in _state_store:
        raise HTTPException(status_code=400, detail={"code": "invalid_state",
                                                     "message": "state نامعتبر یا منقضی است"})
    _state_store.pop(state, None)

    if sso_mode() == "oidc":
        # تبادل code با نقطه پایان Token سامانه مادر
        data = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": _base_url(request) + "/api/v1/auth/sso/callback",
            "client_id": settings.sso_client_id,
            "client_secret": settings.sso_client_secret,
        }).encode()
        req = urllib.request.Request(settings.sso_token_url, data=data, method="POST",
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                token_res = json.loads(res.read().decode())
        except Exception:
            raise HTTPException(status_code=502, detail={
                "code": "sso_provider_error",
                "message": "تبادل توکن با سامانه مادر دانشجو۳۶۰ ناموفق بود"})
        claims: dict = {}
        if token_res.get("id_token"):
            from ..core.security import decode_token_payload
            claims = decode_token_payload(token_res["id_token"]) or {}
        if settings.sso_userinfo_url and token_res.get("access_token"):
            ureq = urllib.request.Request(settings.sso_userinfo_url,
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
            raise HTTPException(status_code=400, detail={"code": "invalid_code",
                                                         "message": "کد احراز نامعتبر یا منقضی است"})
        email, name, master_roles = entry["email"], entry["name"], entry["roles"]

    user = _provision(db, email, name, master_roles)
    log_audit(db, user.id, "sso_login", "user", user.id,
              {"mode": sso_mode(), "master_roles": master_roles}, request)
    db.commit()
    token = create_access_token(user.id)
    return RedirectResponse("/#/sso?token=" + urllib.parse.quote(token), status_code=302)


@router.get("/demo/identities")
def demo_identities():
    return {"items": DEMO_IDENTITIES, "mode": sso_mode()}
