from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, get_memberships, require_roles, require_org_role
from ..db import get_db
from ..models import (
    MemberRole, MembershipStatus, Organization, OrganizationMembership,
    OrganizationVerification, OrgStatus, OrgType, User, utcnow,
)
from ..serializers import org_brief, user_brief
from ..services import log_audit, notify

router = APIRouter(tags=["organizations"])

STAFF_ROLES = {MemberRole.cio_manager, MemberRole.cio_expert, MemberRole.university_admin,
               MemberRole.sys_admin}


class OrgIn(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    org_type: OrgType
    legal_id: str | None = None
    industry_sector: str | None = None
    size: str | None = None
    city: str | None = None
    website: str | None = None
    contact_name: str | None = None
    contact_email: str | None = None
    description: str | None = None


class VerificationRequestIn(BaseModel):
    documents_note: str | None = None


class VerificationDecisionIn(BaseModel):
    decision: str = Field(pattern="^(approved|rejected)$")
    review_note: str | None = None


class MemberIn(BaseModel):
    user_email: str
    role: MemberRole


@router.get("/organizations")
def list_organizations(org_type: str | None = None, status: str | None = None,
                       q: str | None = None, db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    query = db.query(Organization)
    if org_type:
        query = query.filter(Organization.org_type == org_type)
    if status:
        query = query.filter(Organization.status == status)
    if q:
        query = query.filter(or_(Organization.name.ilike(f"%{q}%"),
                                 Organization.industry_sector.ilike(f"%{q}%")))
    orgs = query.order_by(Organization.created_at.desc()).limit(200).all()
    return {"items": [org_brief(o) for o in orgs], "total": len(orgs)}


@router.post("/organizations")
def create_organization(payload: OrgIn, request: Request, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    # جلوگیری از ایجاد سازمان تکراری
    dup_q = db.query(Organization).filter(Organization.name == payload.name.strip())
    if payload.legal_id:
        dup_q = dup_q.filter(or_(Organization.legal_id == payload.legal_id))
    dup = dup_q.first()
    if dup:
        raise HTTPException(status_code=409, detail={
            "code": "duplicate_organization",
            "message": f"سازمانی با این نام/شناسه پیش‌تر ثبت شده و در وضعیت «{ORG_STATUS_FA.get(dup.status.value, dup.status.value)}» است"})

    org = Organization(**payload.model_dump(), status=OrgStatus.pending, created_by=user.id)
    db.add(org)
    db.flush()
    # ثبت‌کننده به‌عنوان اولین نماینده/مدیر سازمان
    default_role = MemberRole.industry_rep if payload.org_type == OrgType.industry else MemberRole.professor
    db.add(OrganizationMembership(user_id=user.id, organization_id=org.id,
                                  role=default_role, status=MembershipStatus.active))
    log_audit(db, user.id, "organization_created", "organization", org.id,
              {"name": org.name}, request)
    db.add(OrganizationVerification(organization_id=org.id, requested_by=user.id,
                                    documents_note="ثبت اولیه سازمان"))
    db.commit()
    return {"id": org.id, **org_brief(org)}


ORG_STATUS_FA = {"pending": "در انتظار احراز", "verified": "تأییدشده",
                 "rejected": "ردشده", "suspended": "معلق"}


@router.get("/organizations/{org_id}")
def get_organization(org_id: str, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "سازمان یافت نشد"})
    memberships = get_memberships(db, user)
    is_member = any(m.organization_id == org.id for m in memberships)
    verifications = []
    if is_member or ({m.role for m in memberships} & STAFF_ROLES):
        verifications = [{
            "id": v.id, "status": v.status, "documents_note": v.documents_note,
            "review_note": v.review_note,
            "created_at": v.created_at.isoformat(),
            "reviewed_at": v.reviewed_at.isoformat() if v.reviewed_at else None,
        } for v in db.query(OrganizationVerification)
            .filter(OrganizationVerification.organization_id == org.id)
            .order_by(OrganizationVerification.created_at.desc()).all()]
    members = []
    if is_member or ({m.role for m in memberships} & STAFF_ROLES):
        ms = db.query(OrganizationMembership).filter(
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.status == MembershipStatus.active).all()
        members = [{"user": user_brief(m.user), "role": m.role.value,
                    "role_label": router_role_label(m.role)} for m in ms]
    return {**org_brief(org), "legal_id": org.legal_id, "size": org.size,
            "website": org.website, "contact_name": org.contact_name,
            "contact_email": org.contact_email if is_member else None,
            "description": org.description,
            "restriction_note": org.restriction_note if is_member else None,
            "verifications": verifications, "members": members,
            "is_member": is_member}


def router_role_label(r: MemberRole) -> str:
    return {
        MemberRole.industry_rep: "نماینده صنعت",
        MemberRole.industry_manager: "مدیر سازمان صنعتی",
        MemberRole.student: "دانشجو",
        MemberRole.professor: "استاد",
        MemberRole.cio_manager: "مدیر دفتر ارتباط با صنعت",
        MemberRole.cio_expert: "کارشناس حوزه تخصصی",
        MemberRole.comm_expert: "کارشناس تجاری‌سازی",
        MemberRole.university_admin: "مدیر دانشگاه",
        MemberRole.policy_maker: "سیاست‌گذار",
        MemberRole.sys_admin: "مدیر فنی",
    }.get(r, r.value)


@router.post("/organizations/{org_id}/verification-requests")
def request_verification(org_id: str, payload: VerificationRequestIn, request: Request,
                         db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "سازمان یافت نشد"})
    memberships = get_memberships(db, user)
    require_org_role(user, memberships, org.id, MemberRole.industry_rep, MemberRole.industry_manager)
    vr = OrganizationVerification(organization_id=org.id, requested_by=user.id,
                                  documents_note=payload.documents_note)
    db.add(vr)
    log_audit(db, user.id, "verification_requested", "organization", org.id, request=request)
    staff = db.query(OrganizationMembership).filter(
        OrganizationMembership.role.in_([MemberRole.cio_manager]),
        OrganizationMembership.status == MembershipStatus.active).all()
    for s in staff:
        notify(db, s.user_id, "درخواست احراز سازمان جدید",
               f"سازمان «{org.name}» درخواست احراز ثبت کرد.", "/review/organizations")
    db.commit()
    return {"id": vr.id, "status": vr.status}


@router.post("/organizations/{org_id}/verification")
def decide_verification(org_id: str, payload: VerificationDecisionIn, request: Request,
                        db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    memberships = get_memberships(db, user)
    require_roles(user, memberships, MemberRole.cio_manager, MemberRole.cio_expert)
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "سازمان یافت نشد"})
    vr = (db.query(OrganizationVerification)
          .filter(OrganizationVerification.organization_id == org.id,
                  OrganizationVerification.status == "pending")
          .order_by(OrganizationVerification.created_at.desc()).first())
    if not vr:
        raise HTTPException(status_code=409, detail={"code": "no_pending_request",
                                                     "message": "درخواست احراز در جریانی برای این سازمان وجود ندارد"})
    vr.status = payload.decision
    vr.reviewed_by = user.id
    vr.review_note = payload.review_note
    vr.reviewed_at = utcnow()
    org.status = OrgStatus.verified if payload.decision == "approved" else OrgStatus.rejected
    log_audit(db, user.id, f"organization_{payload.decision}", "organization", org.id,
              {"note": payload.review_note}, request)
    for m in db.query(OrganizationMembership).filter(
            OrganizationMembership.organization_id == org.id,
            OrganizationMembership.status == MembershipStatus.active).all():
        notify(db, m.user_id, "وضعیت احراز سازمان تغییر کرد",
               f"سازمان «{org.name}» به وضعیت «{ORG_STATUS_FA.get(org.status.value)}» تغییر یافت.",
               f"/organizations/{org.id}")
    db.commit()
    return {"status": org.status.value}


@router.post("/organizations/{org_id}/members")
def add_member(org_id: str, payload: MemberIn, request: Request,
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    org = db.get(Organization, org_id)
    if not org:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "سازمان یافت نشد"})
    memberships = get_memberships(db, user)
    require_org_role(user, memberships, org.id, MemberRole.industry_manager, MemberRole.cio_manager)
    target = db.query(User).filter(User.email == payload.user_email.lower().strip()).first()
    if not target:
        raise HTTPException(status_code=404, detail={"code": "user_not_found",
                                                     "message": "کاربری با این ایمیل یافت نشد"})
    exists = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == target.id,
        OrganizationMembership.organization_id == org.id,
        OrganizationMembership.role == payload.role).first()
    if exists and exists.status == MembershipStatus.active:
        raise HTTPException(status_code=409, detail={"code": "duplicate_membership",
                                                     "message": "این کاربر با همین نقش از قبل عضو سازمان است"})
    if exists:
        exists.status = MembershipStatus.active
    else:
        db.add(OrganizationMembership(user_id=target.id, organization_id=org.id,
                                      role=payload.role, status=MembershipStatus.active))
    log_audit(db, user.id, "member_added", "organization", org.id,
              {"user": target.email, "role": payload.role.value}, request)
    notify(db, target.id, "عضویت در سازمان", f"شما به‌عنوان عضو سازمان «{org.name}» ثبت شدید.")
    db.commit()
    return {"ok": True}


@router.get("/users")
def list_users(q: str | None = None, role: str | None = None, limit: int = 50,
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """جست‌وجوی کاربران برای دعوت به تیم/سازمان — پروفایل حداقلی."""
    from ..models import OrganizationMembership as OM
    query = db.query(User).filter(User.is_active.is_(True))
    if q:
        query = query.filter(or_(User.full_name.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")))
    users = query.limit(min(limit, 100)).all()
    items = []
    for u in users:
        roles = [m.role.value for m in db.query(OM).filter(
            OM.user_id == u.id, OM.status == MembershipStatus.active).all()]
        if role and role not in roles:
            continue
        items.append({**user_brief(u), "roles": roles})
    return {"items": items, "total": len(items)}
