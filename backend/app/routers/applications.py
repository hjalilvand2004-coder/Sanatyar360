"""درخواست همکاری — چرخه: draft/submitted → under_review → shortlisted → accepted/rejected (+withdrawn)"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, get_memberships, is_university_staff
from ..db import get_db
from ..models import (
    AppStatus, Application, ApplicationMember, Attachment, MemberRole,
    OrganizationMembership, TeamMemberStatus, User,
)
from ..routers.problems import can_access_problem
from ..serializers import application_brief, user_brief
from ..services import log_audit, notify

router = APIRouter(tags=["applications"])

INDUSTRY_ROLES = (MemberRole.industry_rep, MemberRole.industry_manager)


def _applicant_visible_skills(db: Session, user_id: str) -> list[dict]:
    from ..models import UserSkillSnapshot
    rows = db.query(UserSkillSnapshot).filter_by(user_id=user_id).all()
    return [{"skill": r.skill.name, "level": r.level, "source": r.source} for r in rows]


def _serialize(db: Session, a: Application, viewer: User, viewer_memberships) -> dict:
    from ..models import Consent, IndustrialProblem
    p = db.get(IndustrialProblem, a.problem_id)
    applicant = db.get(User, a.applicant_user_id)
    full = a.applicant_user_id == viewer.id or is_university_staff(viewer_memberships)
    if not full:
        # رضایت مالک داده؟
        consents = db.query(Consent).filter_by(user_id=a.applicant_user_id,
                                               consent_type="profile_share_industry").all()
        full = any(c.granted and c.revoked_at is None for c in consents)
    members = []
    for m in db.query(ApplicationMember).filter_by(application_id=a.id).all():
        mu = db.get(User, m.user_id)
        members.append({"id": m.id, "user": user_brief(mu, full_access=full),
                        "role": m.role, "status": m.status.value,
                        "skills": _applicant_visible_skills(db, m.user_id)})
    d = application_brief(a, applicant, p.title if p else "—", full_profile=full, members=members)
    if full:
        d["skills"] = _applicant_visible_skills(db, a.applicant_user_id)
    return d


class ApplicationIn(BaseModel):
    proposed_role: str | None = Field(default=None, max_length=80)
    team_name: str | None = Field(default=None, max_length=150)
    fit_statement: str = Field(min_length=20, max_length=4000)
    related_background: str | None = None
    weekly_hours: int = Field(default=10, ge=1, le=60)
    available_from: str | None = None
    initial_plan: str | None = None
    consent_data_share: bool = False
    member_emails: list[str] = []


@router.post("/problems/{problem_id}/applications")
def create_application(problem_id: str, payload: ApplicationIn, request: Request,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from ..models import IndustrialProblem, ProblemStatus
    p = db.get(IndustrialProblem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "مسئله یافت نشد"})
    memberships = get_memberships(db, user)
    if user.user_type not in ("student", "professor"):
        raise HTTPException(status_code=403, detail={
            "code": "forbidden", "message": "درخواست همکاری فقط برای دانشجو و استاد مجاز است"})
    if p.status != ProblemStatus.published:
        raise HTTPException(status_code=409, detail={
            "code": "invalid_state", "message": "درخواست همکاری فقط برای مسئله منتشرشده امکان‌پذیر است"})
    if p.application_deadline:
        from ..models import as_utc
        if as_utc(utcnow()) > as_utc(p.application_deadline):
            raise HTTPException(status_code=409, detail={
                "code": "deadline_passed", "message": "مهلت درخواست این مسئله گذشته است"})
    if can_access_problem(db, user, memberships, p) is not None:
        raise HTTPException(status_code=403, detail={"code": "confidential",
                                                     "message": "دسترسی به این مسئله ندارید"})
    dup = db.query(Application).filter_by(problem_id=problem_id, applicant_user_id=user.id).first()
    if dup and dup.status != AppStatus.withdrawn:
        raise HTTPException(status_code=409, detail={"code": "duplicate_application",
                                                     "message": "شما قبلاً برای این مسئله درخواست ثبت کرده‌اید"})
    if payload.consent_data_share:
        from ..models import Consent
        db.add(Consent(user_id=user.id, consent_type="profile_share_industry", granted=True,
                       scope_text="اشتراک پروفایل حداقلی با سازمان مالک مسئله و دفتر ارتباط با صنعت"))
    a = Application(problem_id=problem_id, applicant_user_id=user.id,
                    **{k: v for k, v in payload.model_dump().items() if k != "member_emails"},
                    status=AppStatus.submitted)
    db.add(a)
    db.flush()
    for email in payload.member_emails[:10]:
        mu = db.query(User).filter(User.email == email.lower().strip()).first()
        if mu and mu.id != user.id:
            db.add(ApplicationMember(application_id=a.id, user_id=mu.id,
                                     status=TeamMemberStatus.invited))
            notify(db, mu.id, "دعوت به تیم درخواست همکاری",
                   f"«{user.full_name}» شما را به تیم درخواست «{p.title}» دعوت کرد.",
                   f"/applications/{a.id}")
    log_audit(db, user.id, "application_submitted", "application", a.id,
              {"problem_id": problem_id}, request)
    notify(db, p.created_by, "درخواست همکاری جدید",
           f"برای مسئله «{p.title}» درخواست جدید ثبت شد.", f"/problems/{problem_id}")
    db.commit()
    return _serialize(db, a, user, memberships)


@router.get("/applications")
def list_my_applications(status: str | None = None, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    memberships = get_memberships(db, user)
    query = db.query(Application)
    if is_university_staff(memberships) or any(m.role in INDUSTRY_ROLES for m in memberships):
        pass  # نقش‌های سازمانی از مسیر مسئله می‌بینند؛ اینجا درخواست‌های خود کاربر
    query = query.filter((Application.applicant_user_id == user.id) |
                         (Application.id.in_(
                             db.query(ApplicationMember.application_id)
                             .filter(ApplicationMember.user_id == user.id))))
    if status:
        query = query.filter(Application.status == status)
    apps = query.order_by(Application.created_at.desc()).all()
    return {"items": [_serialize(db, a, user, memberships) for a in apps], "total": len(apps)}


@router.get("/applications/{app_id}")
def get_application(app_id: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    a = db.get(Application, app_id)
    if not a:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "درخواست یافت نشد"})
    memberships = get_memberships(db, user)
    from ..models import IndustrialProblem
    p = db.get(IndustrialProblem, a.problem_id)
    is_owner_rep = any(m.organization_id == p.owner_organization_id and m.role in INDUSTRY_ROLES
                       for m in memberships)
    staff = is_university_staff(memberships)
    involved = (a.applicant_user_id == user.id or
                db.query(ApplicationMember).filter_by(application_id=a.id, user_id=user.id).first())
    if not (is_owner_rep or staff or involved):
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                     "message": "دسترسی غیرمجاز به این درخواست"})
    return _serialize(db, a, user, memberships)


class MemberInviteIn(BaseModel):
    user_email: str
    role: str | None = None


@router.post("/applications/{app_id}/members")
def invite_member(app_id: str, payload: MemberInviteIn, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    a = db.get(Application, app_id)
    if not a:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "درخواست یافت نشد"})
    if a.applicant_user_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                     "message": "فقط متقاضی می‌تواند عضو دعوت کند"})
    if a.status not in (AppStatus.submitted, AppStatus.under_review, AppStatus.shortlisted):
        raise HTTPException(status_code=409, detail={"code": "invalid_state",
                                                     "message": "دعوت در این وضعیت ممکن نیست"})
    mu = db.query(User).filter(User.email == payload.user_email.lower().strip()).first()
    if not mu:
        raise HTTPException(status_code=404, detail={"code": "user_not_found",
                                                     "message": "کاربر یافت نشد"})
    dup = db.query(ApplicationMember).filter_by(application_id=a.id, user_id=mu.id).first()
    if dup:
        raise HTTPException(status_code=409, detail={"code": "duplicate",
                                                     "message": "این کاربر قبلاً دعوت شده است"})
    m = ApplicationMember(application_id=a.id, user_id=mu.id, role=payload.role,
                          status=TeamMemberStatus.invited)
    db.add(m)
    db.flush()
    notify(db, mu.id, "دعوت به تیم درخواست همکاری",
           f"«{user.full_name}» شما را به تیم خود دعوت کرد.", f"/applications/{a.id}")
    db.commit()
    return {"id": m.id, "status": m.status.value}


@router.post("/applications/{app_id}/members/{member_id}/respond")
def respond_member(app_id: str, member_id: str, payload: dict,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    m = db.get(ApplicationMember, member_id)
    if not m or m.application_id != app_id:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "دعوت یافت نشد"})
    if m.user_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                     "message": "فقط کاربر دعوت‌شده می‌تواند پاسخ دهد"})
    accept = bool(payload.get("accept"))
    m.status = TeamMemberStatus.accepted if accept else TeamMemberStatus.declined
    db.commit()
    return {"status": m.status.value}


class DecisionIn(BaseModel):
    decision: str = Field(pattern="^(shortlist|accept|reject)$")
    reason: str | None = Field(default=None, max_length=2000)


@router.post("/applications/{app_id}/decisions")
def decide_application(app_id: str, payload: DecisionIn, request: Request,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = db.get(Application, app_id)
    if not a:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "درخواست یافت نشد"})
    memberships = get_memberships(db, user)
    from ..models import IndustrialProblem
    p = db.get(IndustrialProblem, a.problem_id)
    is_owner_rep = any(m.organization_id == p.owner_organization_id and m.role in INDUSTRY_ROLES
                       for m in memberships)
    is_cio = {m.role for m in memberships} & {MemberRole.cio_manager, MemberRole.cio_expert}
    # انتخاب نهایی انسانی و قابل حسابرسی (AC-07)
    if payload.decision in ("accept", "reject"):
        if not is_owner_rep:
            raise HTTPException(status_code=403, detail={
                "code": "forbidden", "message": "پذیرش/عدم پذیرش نهایی فقط توسط نماینده سازمان مالک انجام می‌شود"})
        if not payload.reason or len(payload.reason.strip()) < 5:
            raise HTTPException(status_code=422, detail={
                "code": "reason_required", "message": "ثبت دلیل تصمیم برای پذیرش/عدم پذیرش الزامی است"})
        new_status = AppStatus.accepted if payload.decision == "accept" else AppStatus.rejected
        if a.status not in (AppStatus.submitted, AppStatus.under_review, AppStatus.shortlisted):
            raise HTTPException(status_code=409, detail={"code": "invalid_state",
                                                         "message": "درخواست در وضعیت قابل تصمیم‌گیری نیست"})
    else:  # shortlist — صنعت مالک یا دفتر
        if not (is_owner_rep or is_cio):
            raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                         "message": "دسترسی غیرمجاز"})
        new_status = AppStatus.shortlisted
        if a.status not in (AppStatus.submitted, AppStatus.under_review):
            raise HTTPException(status_code=409, detail={"code": "invalid_state",
                                                         "message": "فهرست کوتاه در این وضعیت ممکن نیست"})
    if a.status == AppStatus.submitted:
        a.status = AppStatus.under_review
    a.status = new_status
    a.decision_reason = payload.reason
    a.decided_by = user.id
    from ..models import utcnow
    a.decided_at = utcnow()
    log_audit(db, user.id, f"application_{payload.decision}", "application", a.id,
              {"reason": payload.reason}, request)
    notify(db, a.applicant_user_id, "وضعیت درخواست همکاری تغییر کرد",
           f"درخواست شما برای «{p.title}» به وضعیت «{STATUS_FA[new_status.value]}» تغییر کرد."
           + (f" دلیل: {payload.reason}" if payload.reason else ""),
           f"/applications/{a.id}")
    for m in db.query(ApplicationMember).filter_by(application_id=a.id,
                                                   status=TeamMemberStatus.accepted).all():
        notify(db, m.user_id, "وضعیت درخواست تیم تغییر کرد",
               f"درخواست «{p.title}» به وضعیت «{STATUS_FA[new_status.value]}» تغییر کرد.")
    db.commit()
    return {"status": a.status.value}


@router.post("/applications/{app_id}/withdraw")
def withdraw_application(app_id: str, request: Request, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    a = db.get(Application, app_id)
    if not a:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "درخواست یافت نشد"})
    if a.applicant_user_id != user.id:
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                     "message": "فقط متقاضی می‌تواند درخواست را پس بگیرد"})
    if a.status in (AppStatus.accepted, AppStatus.rejected, AppStatus.withdrawn):
        raise HTTPException(status_code=409, detail={"code": "invalid_state",
                                                     "message": "درخواست در وضعیت قابل پس‌گرفتن نیست"})
    a.status = AppStatus.withdrawn
    log_audit(db, user.id, "application_withdrawn", "application", a.id, request=request)
    db.commit()
    return {"status": a.status.value}


@router.get("/problems/{problem_id}/applications")
def list_problem_applications(problem_id: str, db: Session = Depends(get_db),
                              user: User = Depends(get_current_user)):
    from ..models import IndustrialProblem
    p = db.get(IndustrialProblem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "مسئله یافت نشد"})
    memberships = get_memberships(db, user)
    is_owner_rep = any(m.organization_id == p.owner_organization_id and m.role in INDUSTRY_ROLES
                       for m in memberships)
    staff = is_university_staff(memberships)
    if not (is_owner_rep or staff):
        raise HTTPException(status_code=403, detail={
            "code": "forbidden", "message": "مشاهده متقاضیان فقط برای سازمان مالک و دفتر ارتباط با صنعت مجاز است"})
    apps = db.query(Application).filter_by(problem_id=problem_id).order_by(
        Application.created_at.desc()).all()
    return {"items": [_serialize(db, a, user, memberships) for a in apps], "total": len(apps)}


STATUS_FA = {
    "submitted": "ثبت‌شده", "under_review": "در بررسی", "shortlisted": "فهرست کوتاه",
    "accepted": "پذیرفته‌شده", "rejected": "ردشده", "withdrawn": "پس‌گرفته‌شده",
    "draft": "پیش‌نویس",
}
