from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, get_memberships
from ..core.security import (create_access_token, decode_token_payload,
                             register_session, revoke_session, verify_password)
from ..db import get_db
from ..models import Consent, MemberRole, User, utcnow
from ..serializers import user_brief
from ..services import log_audit

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


def _me_payload(db: Session, user: User) -> dict:
    memberships = get_memberships(db, user)
    consents = db.query(Consent).filter(Consent.user_id == user.id).all()
    return {
        "user": user_brief(user, full_access=True),
        "memberships": [
            {
                "organization_id": m.organization_id,
                "organization_name": m.organization.name,
                "org_type": m.organization.org_type.value,
                "org_status": m.organization.status.value,
                "role": m.role.value,
                "role_label": ROLE_LABELS.get(m.role, m.role.value),
            }
            for m in memberships
        ],
        "consents": [
            {"consent_type": c.consent_type, "granted": c.granted,
             "revoked": c.revoked_at is not None}
            for c in consents
        ],
    }


ROLE_LABELS = {
    MemberRole.industry_rep: "نماینده صنعت",
    MemberRole.industry_manager: "مدیر سازمان صنعتی",
    MemberRole.student: "دانشجو",
    MemberRole.professor: "استاد",
    MemberRole.cio_manager: "مدیر دفتر ارتباط با صنعت",
    MemberRole.cio_expert: "کارشناس حوزه تخصصی",
    MemberRole.comm_expert: "کارشناس تجاری‌سازی",
    MemberRole.university_admin: "مدیر دانشگاه",
    MemberRole.policy_maker: "سیاست‌گذار",
    MemberRole.sys_admin: "مدیر فنی سامانه",
}


@router.post("/login")
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower().strip()).first()
    # پیام خطای یکسان برای جلوگیری از افشای وجود ایمیل
    if not user or not verify_password(payload.password, user.password_hash):
        log_audit(db, None, "login_failed", "user", detail={"email": payload.email}, request=request)
        db.commit()
        raise HTTPException(status_code=401, detail={"code": "invalid_credentials",
                                                     "message": "ایمیل یا رمز عبور نادرست است"})
    if not user.is_active:
        raise HTTPException(status_code=403, detail={"code": "inactive",
                                                     "message": "حساب کاربر غیرفعال است"})
    log_audit(db, user.id, "login", "user", user.id, request=request)
    token = create_access_token(user.id)
    register_session(db, token, user.id)   # ثبت برای قابلیت ابطال نشست
    db.commit()
    return {"access_token": token, "token_type": "bearer", **_me_payload(db, user)}


@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db),
           user: User = Depends(get_current_user)):
    """ابطال نشست جاری — توکن پس از این فراخوانی دیگر پذیرفته نمی‌شود."""
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:].strip() if auth_header.startswith("Bearer ") else ""
    claims = decode_token_payload(token) if token else {}
    jti = claims.get("jti")
    revoked = revoke_session(db, jti) if jti else False
    log_audit(db, user.id, "logout", "user", user.id, {"revoked": revoked}, request)
    db.commit()
    return {"ok": True, "revoked": revoked}


@router.get("/me")
def me(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _me_payload(db, user)
