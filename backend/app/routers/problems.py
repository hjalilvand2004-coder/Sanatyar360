"""ماژول مسئله صنعتی — چرخه: draft → submitted → under_review → needs_revision/published → ..."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from ..core.deps import get_current_user, get_memberships, is_university_staff
from ..db import get_db
from ..models import (
    Application, Confidentiality, IndustrialProblem, MemberRole, MembershipStatus,
    OrganizationMembership, ProblemInterest, ProblemQuestion, ProblemRequiredSkill,
    ProblemReview, ProblemStatus, ProblemVersion, ReviewDecision, Skill, User,
    WorkMode,
)
from ..serializers import problem_brief, problem_detail
from ..services import log_audit, notify

router = APIRouter(prefix="/problems", tags=["problems"])

# الزامات انتشار (کنترل کیفیت — AC-02)
QUALITY_FIELDS = {
    "summary": "خلاصه عمومی",
    "description": "شرح کامل وضعیت و مسئله",
    "expected_outcomes": "خروجی مورد انتظار (تحویل‌دادنی‌ها)",
    "acceptance_criteria": "معیار پذیرش",
    "contact_name": "مسئول پاسخ‌گویی",
    "ip_policy_summary": "شرایط مالکیت فکری",
}


def can_access_problem(db: Session, user: User, memberships: list[OrganizationMembership],
                       p: IndustrialProblem) -> str | None:
    """None = دسترسی کامل؛ 'summary_only' = فقط خلاصه؛ 'none' = بدون دسترسی."""
    owner_ids = {m.organization_id for m in memberships}
    roles = {m.role for m in memberships}
    staff = is_university_staff(memberships)
    if p.owner_organization_id in owner_ids or staff:
        return None
    conf = p.confidentiality_level
    if conf == Confidentiality.public:
        return None
    if conf == Confidentiality.registered_users:
        return None
    if conf == Confidentiality.selected_participants:
        # فقط متقاضیان/علاقه‌مندانی که در جریان مسئله‌اند یا پیشنهاد سامانه دریافت کرده‌اند
        has_app = db.query(ProblemInterest).filter_by(problem_id=p.id, user_id=user.id).first() is not None
        from ..models import Application
        has_applied = db.query(Application).filter_by(problem_id=p.id, applicant_user_id=user.id).first() is not None
        return None if (has_app or has_applied) else "none"
    if conf == Confidentiality.confidential:
        return "none"
    return "none"


class ProblemIn(BaseModel):
    title: str = Field(min_length=5, max_length=250)
    summary: str = Field(min_length=10, max_length=2000)
    description: str = Field(min_length=30)
    category: str | None = None
    industry_code: str | None = None
    expected_outcomes: list[str] = []
    acceptance_criteria: list[str] = []
    required_team_size: int = Field(default=2, ge=1, le=50)
    duration_days: int | None = Field(default=None, ge=1)
    budget_min: float | None = Field(default=None, ge=0)
    budget_max: float | None = Field(default=None, ge=0)
    currency: str = "IRR"
    budget_confirmed: bool = False
    work_mode: WorkMode = WorkMode.hybrid
    location: str | None = None
    resources_offered: str | None = None
    confidentiality_level: Confidentiality = Confidentiality.public
    ip_policy_summary: str | None = None
    nda_required: bool = False
    application_deadline: str | None = None  # ISO date
    desired_start: str | None = None
    contact_name: str | None = None
    contact_channel: str | None = None
    skill_names: list[str] = []


def _parse_deadline(s: str | None):
    if not s:
        return None
    from datetime import datetime, timezone
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except ValueError:
        return None


def _upsert_skills(db: Session, p: IndustrialProblem, names: list[str]):
    p.required_skills.clear()
    db.flush()
    for name in names:
        name = name.strip()
        if not name:
            continue
        skill = db.query(Skill).filter(Skill.name == name).first()
        if not skill:
            skill = Skill(name=name)
            db.add(skill)
            db.flush()
        db.add(ProblemRequiredSkill(problem_id=p.id, skill_id=skill.id, min_level=2, is_required=True))


def _snapshot_version(db: Session, p: IndustrialProblem, user_id: str):
    db.add(ProblemVersion(problem_id=p.id, version=p.version,
                          payload=problem_detail(p), changed_by=user_id))


@router.get("")
def list_problems(status: str | None = None, q: str | None = None, category: str | None = None,
                  work_mode: str | None = None, sector: str | None = None,
                  skill: str | None = None, mine: bool = False, limit: int = 50, offset: int = 0,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    memberships = get_memberships(db, user)
    staff = is_university_staff(memberships)
    owner_ids = {m.organization_id for m in memberships}
    visible_statuses = [ProblemStatus.published, ProblemStatus.applications_closed,
                        ProblemStatus.converted_to_project]
    query = db.query(IndustrialProblem).options(joinedload(IndustrialProblem.owner),
                                                joinedload(IndustrialProblem.required_skills))
    if mine:
        query = query.filter(IndustrialProblem.owner_organization_id.in_(owner_ids))
    elif not staff:
        # AC-03: مسائل محرمانه سازمان دیگر دیده نمی‌شود
        query = query.filter(or_(
            IndustrialProblem.confidentiality_level.in_(
                [Confidentiality.public, Confidentiality.registered_users]),
            IndustrialProblem.owner_organization_id.in_(owner_ids),
        ))
    if status:
        query = query.filter(IndustrialProblem.status == status)
    elif not mine and not staff:
        query = query.filter(IndustrialProblem.status == ProblemStatus.published)
    if q:
        query = query.filter(or_(IndustrialProblem.title.ilike(f"%{q}%"),
                                 IndustrialProblem.summary.ilike(f"%{q}%")))
    if category:
        query = query.filter(IndustrialProblem.category == category)
    if work_mode:
        query = query.filter(IndustrialProblem.work_mode == work_mode)
    if sector:
        query = query.filter(IndustrialProblem.industry_code == sector)
    if skill:
        query = query.join(ProblemRequiredSkill).join(Skill).filter(Skill.name == skill)
    total = query.count()
    items = query.order_by(IndustrialProblem.created_at.desc()).offset(offset).limit(min(limit, 100)).all()
    return {"items": [problem_brief(p) for p in items], "total": total,
            "limit": limit, "offset": offset}


class ProblemOut(BaseModel):
    pass


@router.post("")
def create_problem(payload: ProblemIn, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    memberships = get_memberships(db, user)
    industry_orgs = [m.organization_id for m in memberships
                     if m.role in (MemberRole.industry_rep, MemberRole.industry_manager)]
    org_id = request.query_params.get("org_id") or (industry_orgs[0] if industry_orgs else None)
    if not org_id or org_id not in industry_orgs:
        raise HTTPException(status_code=403, detail={
            "code": "forbidden_org_scope",
            "message": "ثبت مسئله فقط توسط نماینده صنعت یا مدیر سازمان صنعتی در سازمان خودش امکان‌پذیر است"})
    if payload.budget_min and payload.budget_max and payload.budget_min > payload.budget_max:
        raise HTTPException(status_code=422, detail={"code": "validation",
                                                     "message": "حداقل بودجه نمی‌تواند بیشتر از حداکثر باشد"})
    p = IndustrialProblem(
        **{k: v for k, v in payload.model_dump().items() if k not in ("skill_names", "application_deadline")},
        owner_organization_id=org_id, created_by=user.id,
        application_deadline=_parse_deadline(payload.application_deadline))
    db.add(p)
    db.flush()
    _upsert_skills(db, p, payload.skill_names)
    _snapshot_version(db, p, user.id)
    log_audit(db, user.id, "problem_created", "industrial_problem", p.id, {"title": p.title}, request)
    db.commit()
    return problem_detail(p)


@router.get("/{problem_id}")
def get_problem(problem_id: str, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    p = db.get(IndustrialProblem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "مسئله یافت نشد"})
    memberships = get_memberships(db, user)
    access = can_access_problem(db, user, memberships, p)
    if access == "none":
        raise HTTPException(status_code=403, detail={
            "code": "confidential",
            "message": "این مسئله محرمانه است و دسترسی شما به آن مجاز نیست"})
    if access == "summary_only":
        d = problem_brief(p)
        d["restricted_access"] = True
        return d
    d = problem_detail(p)
    d["restricted_access"] = False
    interest = db.query(ProblemInterest).filter_by(problem_id=p.id, user_id=user.id).first()
    d["my_interest"] = interest is not None
    d["my_application"] = db.query(Application).filter_by(
        problem_id=p.id, applicant_user_id=user.id).first() is not None
    d["interests_count"] = db.query(ProblemInterest).filter_by(problem_id=p.id).count()
    return d


@router.patch("/{problem_id}")
def update_problem(problem_id: str, payload: ProblemIn, request: Request,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = db.get(IndustrialProblem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "مسئله یافت نشد"})
    memberships = get_memberships(db, user)
    is_owner = any(m.organization_id == p.owner_organization_id and
                   m.role in (MemberRole.industry_rep, MemberRole.industry_manager)
                   for m in memberships)
    if not is_owner:
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                     "message": "فقط نماینده سازمان مالک می‌تواند مسئله را ویرایش کند"})
    if p.status not in (ProblemStatus.draft, ProblemStatus.needs_revision):
        raise HTTPException(status_code=409, detail={
            "code": "invalid_state",
            "message": f"ویرایش در وضعیت «{p.status.value}» مجاز نیست؛ فقط پیش‌نویس یا نیازمند اصلاح قابل ویرایش است (نسخه‌بندی)"})
    data = payload.model_dump()
    skill_names = data.pop("skill_names")
    data["application_deadline"] = _parse_deadline(data.get("application_deadline"))
    for k, v in data.items():
        setattr(p, k, v)
    p.version += 1
    _upsert_skills(db, p, skill_names)
    _snapshot_version(db, p, user.id)
    log_audit(db, user.id, "problem_updated", "industrial_problem", p.id,
              {"version": p.version}, request)
    db.commit()
    return problem_detail(p)


@router.post("/{problem_id}/submit")
def submit_problem(problem_id: str, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    p = db.get(IndustrialProblem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "مسئله یافت نشد"})
    memberships = get_memberships(db, user)
    is_owner = any(m.organization_id == p.owner_organization_id and
                   m.role in (MemberRole.industry_rep, MemberRole.industry_manager)
                   for m in memberships)
    if not is_owner:
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                     "message": "فقط نماینده سازمان مالک می‌تواند مسئله را ارسال کند"})
    if p.status not in (ProblemStatus.draft, ProblemStatus.needs_revision):
        raise HTTPException(status_code=409, detail={"code": "invalid_state",
                                                     "message": "این مسئله در وضعیت قابل ارسال نیست"})
    p.status = ProblemStatus.submitted
    log_audit(db, user.id, "problem_submitted", "industrial_problem", p.id, request=request)
    for m in db.query(OrganizationMembership).filter(
            OrganizationMembership.role.in_([MemberRole.cio_manager, MemberRole.cio_expert]),
            OrganizationMembership.status == MembershipStatus.active).all():
        notify(db, m.user_id, "مسئله صنعتی جدید در صف بررسی",
               f"«{p.title}» برای بررسی ارسال شد.", f"/problems/{p.id}")
    db.commit()
    return {"status": p.status.value}


@router.post("/{problem_id}/reviews")
def review_problem(problem_id: str, payload: dict, request: Request,
                   db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    decision = payload.get("decision")
    note = (payload.get("note") or "").strip()
    if decision not in ("approve", "needs_revision", "reject"):
        raise HTTPException(status_code=422, detail={"code": "validation",
                                                     "message": "decision باید approve/needs_revision/reject باشد"})
    if decision in ("needs_revision", "reject") and not note:
        raise HTTPException(status_code=422, detail={"code": "validation",
                                                     "message": "ثبت دلیل برای اصلاح/رد الزامی است"})
    memberships = get_memberships(db, user)
    if not ({m.role for m in memberships} & {MemberRole.cio_manager, MemberRole.cio_expert}):
        raise HTTPException(status_code=403, detail={
            "code": "forbidden", "message": "بررسی مسئله فقط توسط دفتر ارتباط با صنعت یا کارشناس حوزه تخصصی مجاز است"})
    p = db.get(IndustrialProblem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "مسئله یافت نشد"})
    if p.status not in (ProblemStatus.submitted, ProblemStatus.under_review):
        raise HTTPException(status_code=409, detail={"code": "invalid_state",
                                                     "message": "مسئله در وضعیت قابل بررسی نیست"})
    if p.status == ProblemStatus.submitted:
        p.status = ProblemStatus.under_review
    db.add(ProblemReview(problem_id=p.id, reviewer_id=user.id,
                         decision=ReviewDecision(decision), note=note or None))
    log_audit(db, user.id, f"problem_review_{decision}", "industrial_problem", p.id,
              {"note": note}, request)
    if decision == "needs_revision":
        p.status = ProblemStatus.needs_revision
        p.rejection_reason = note
        notify(db, p.created_by, "مسئله نیازمند اصلاح", note, f"/problems/{p.id}")
    elif decision == "reject":
        p.status = ProblemStatus.rejected
        p.rejection_reason = note
        notify(db, p.created_by, "مسئله رد شد", note, f"/problems/{p.id}")
    else:
        notify(db, p.created_by, "بررسی مثبت مسئله",
               "بررسی تخصصی با تأیید همراه بود؛ پس از انتشار اطلاع رسانی می‌شود.", f"/problems/{p.id}")
    db.commit()
    return {"status": p.status.value}


@router.post("/{problem_id}/publish")
def publish_problem(problem_id: str, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    memberships = get_memberships(db, user)
    if not ({m.role for m in memberships} & {MemberRole.cio_manager, MemberRole.cio_expert}):
        raise HTTPException(status_code=403, detail={
            "code": "forbidden", "message": "انتشار فقط توسط دفتر ارتباط با صنعت مجاز است"})
    p = db.get(IndustrialProblem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "مسئله یافت نشد"})
    # AC-02 + قواعد کنترل کیفیت: انتشار منوط به تأیید قبلی و کامل بودن اطلاعات
    if p.status not in (ProblemStatus.under_review, ProblemStatus.needs_revision):
        raise HTTPException(status_code=409, detail={
            "code": "invalid_state", "message": "تنها مسئله در جریان بررسی می‌تواند منتشر شود"})
    approved = db.query(ProblemReview).filter_by(problem_id=p.id, decision=ReviewDecision.approve).count()
    if approved == 0:
        raise HTTPException(status_code=409, detail={
            "code": "not_approved", "message": "تنها مسئله تأییدشده می‌تواند منتشر شود؛ ابتدا بررسی تأیید ثبت شود"})
    org = p.owner
    if org.status != "verified":
        raise HTTPException(status_code=409, detail={
            "code": "org_not_verified", "message": "سازمان مالک هنوز احراز نشده است"})
    missing = []
    d = p.__dict__
    for f, label in QUALITY_FIELDS.items():
        v = getattr(p, f, None)
        if v is None or (isinstance(v, (list, str)) and not v):
            missing.append(label)
    if missing:
        raise HTTPException(status_code=422, detail={
            "code": "quality_gate_failed",
            "message": "انتشار نیازمند این موارد است: " + "؛ ".join(missing)})
    p.status = ProblemStatus.published
    log_audit(db, user.id, "problem_published", "industrial_problem", p.id, request=request)
    # رویداد Outbox برای اطلاع‌رسانی بین‌سیستمی
    from ..services import add_outbox
    add_outbox(db, "problem.published", {"problem_id": p.id, "title": p.title,
                                         "confidentiality": p.confidentiality_level.value},
               dedupe_key=f"problem.published:{p.id}:{p.version}")
    db.commit()
    return {"status": p.status.value}


@router.post("/{problem_id}/close")
def close_problem(problem_id: str, request: Request, payload: dict | None = None,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = db.get(IndustrialProblem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "مسئله یافت نشد"})
    memberships = get_memberships(db, user)
    is_owner = any(m.organization_id == p.owner_organization_id and
                   m.role in (MemberRole.industry_rep, MemberRole.industry_manager)
                   for m in memberships)
    staff = {m.role for m in memberships} & {MemberRole.cio_manager, MemberRole.cio_expert}
    if not (is_owner or staff):
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                     "message": "دسترسی غیرمجاز"})
    if p.status != ProblemStatus.published:
        raise HTTPException(status_code=409, detail={"code": "invalid_state",
                                                     "message": "بستن فراخوان فقط برای مسئله منتشرشده مجاز است"})
    p.status = ProblemStatus.applications_closed
    log_audit(db, user.id, "problem_closed", "industrial_problem", p.id,
              {"reason": (payload or {}).get("reason")}, request)
    db.commit()
    return {"status": p.status.value}


@router.get("/{problem_id}/questions")
def list_questions(problem_id: str, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    p = db.get(IndustrialProblem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "مسئله یافت نشد"})
    memberships = get_memberships(db, user)
    if can_access_problem(db, user, memberships, p) is not None:
        raise HTTPException(status_code=403, detail={"code": "confidential",
                                                     "message": "دسترسی به این مسئله ندارید"})
    qs = db.query(ProblemQuestion).filter_by(problem_id=problem_id).order_by(
        ProblemQuestion.created_at.desc()).all()
    return {"items": [{
        "id": q.id, "question": q.question, "answer": q.answer,
        "user": {"id": q.user_id, "full_name": _user_name(db, q.user_id)},
        "created_at": q.created_at.isoformat(),
    } for q in qs], "total": len(qs)}


class QuestionIn(BaseModel):
    question: str = Field(min_length=5, max_length=1000)


@router.post("/{problem_id}/questions")
def ask_question(problem_id: str, payload: QuestionIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    p = db.get(IndustrialProblem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "مسئله یافت نشد"})
    memberships = get_memberships(db, user)
    if can_access_problem(db, user, memberships, p) is not None:
        raise HTTPException(status_code=403, detail={"code": "confidential",
                                                     "message": "دسترسی به این مسئله ندارید"})
    q = ProblemQuestion(problem_id=p.id, user_id=user.id, question=payload.question)
    db.add(q)
    db.commit()
    return {"id": q.id}


@router.post("/{problem_id}/questions/{question_id}/answer")
def answer_question(problem_id: str, question_id: str, payload: dict,
                    request: Request, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    q = db.get(ProblemQuestion, question_id)
    if not q or q.problem_id != problem_id:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "پرسش یافت نشد"})
    p = db.get(IndustrialProblem, problem_id)
    memberships = get_memberships(db, user)
    is_owner = any(m.organization_id == p.owner_organization_id and
                   m.role in (MemberRole.industry_rep, MemberRole.industry_manager)
                   for m in memberships)
    staff = {m.role for m in memberships} & {MemberRole.cio_manager, MemberRole.cio_expert}
    if not (is_owner or staff):
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                     "message": "پاسخ‌دهی فقط برای نماینده صنعت/دفتر مجاز است"})
    q.answer = payload.get("answer", "").strip()
    q.answered_by = user.id
    notify(db, q.user_id, "پاسخ به پرسش شما ثبت شد", (q.answer or "")[:120], f"/problems/{p.id}")
    log_audit(db, user.id, "question_answered", "problem_question", q.id, request=request)
    db.commit()
    return {"ok": True}


@router.post("/{problem_id}/interests")
def toggle_interest(problem_id: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    p = db.get(IndustrialProblem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "مسئله یافت نشد"})
    existing = db.query(ProblemInterest).filter_by(problem_id=p.id, user_id=user.id).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"interested": False}
    db.add(ProblemInterest(problem_id=p.id, user_id=user.id))
    db.commit()
    return {"interested": True}


@router.get("/{problem_id}/versions")
def problem_versions(problem_id: str, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    memberships = get_memberships(db, user)
    p = db.get(IndustrialProblem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "مسئله یافت نشد"})
    is_owner = any(m.organization_id == p.owner_organization_id for m in memberships)
    staff = is_university_staff(memberships)
    if not (is_owner or staff):
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                     "message": "دسترسی غیرمجاز"})
    vs = db.query(ProblemVersion).filter_by(problem_id=problem_id).order_by(
        ProblemVersion.version.desc()).all()
    return {"items": [{"version": v.version, "created_at": v.created_at.isoformat(),
                       "changed_by": v.changed_by} for v in vs], "total": len(vs)}


@router.get("/{problem_id}/reviews")
def problem_reviews(problem_id: str, db: Session = Depends(get_db),
                    user: User = Depends(get_current_user)):
    memberships = get_memberships(db, user)
    p = db.get(IndustrialProblem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "مسئله یافت نشد"})
    is_owner = any(m.organization_id == p.owner_organization_id for m in memberships)
    staff = is_university_staff(memberships)
    if not (is_owner or staff):
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                     "message": "دسترسی غیرمجاز"})
    rs = db.query(ProblemReview).filter_by(problem_id=problem_id).order_by(
        ProblemReview.created_at.desc()).all()
    return {"items": [{
        "id": r.id, "decision": r.decision.value, "note": r.note,
        "reviewer": {"id": r.reviewer_id, "full_name": _user_name(db, r.reviewer_id)},
        "created_at": r.created_at.isoformat(),
    } for r in rs], "total": len(rs)}


def _user_name(db: Session, user_id: str) -> str:
    u = db.get(User, user_id)
    return u.full_name if u else "—"
