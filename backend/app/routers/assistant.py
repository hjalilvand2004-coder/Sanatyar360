"""دستیار هوشمند «از نیاز صنعتی تا پروژه» — پرسش‌گری، پیش‌نویس استاندارد، تأیید انسانی.

مسیر: نیاز مبهم ← پاسخ پرسش‌های راهنما ← پیش‌نویس مسئله (با برآورد پرچم‌دار)
← تأیید کارشناس/نماینده صنعت ← ثبت مسئله واقعی در چرخهٔ عادی (بررسی ← انتشار).

دسترسی: نماینده/مدیر صنعت (سازمان خودشان) و مدیر/کارشناس دفتر ارتباط با صنعت.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, get_memberships, require_roles
from ..db import get_db
from ..models import (AssistantIntake, Confidentiality, IndustrialProblem,
                      MemberRole, ProblemStatus, User, utcnow, WorkMode)
from ..services import log_audit
from ..services.assistant import ALGORITHM_VERSION, build_draft, questionnaire
from ..serializers import problem_detail

router = APIRouter(prefix="/assistant", tags=["assistant"])

ALLOWED = (MemberRole.industry_rep, MemberRole.industry_manager,
           MemberRole.cio_manager, MemberRole.cio_expert)
INDUSTRY = (MemberRole.industry_rep, MemberRole.industry_manager)


class IntakeIn(BaseModel):
    answers: dict[str, str] = Field(default_factory=dict)
    organization_id: str | None = None   # الزامی برای نقش‌های صنعت؛ اختیاری برای دفتر ارتباط


def _my_industry_orgs(db, user) -> list[str]:
    memberships = get_memberships(db, user)
    return [m.organization_id for m in memberships if m.role in INDUSTRY]


def _can_manage(db, user, intake) -> bool:
    memberships = get_memberships(db, user)
    if any(m.role in INDUSTRY and m.organization_id == intake.organization_id
           for m in memberships):
        return True
    if ({m.role for m in memberships} & {MemberRole.cio_manager, MemberRole.cio_expert}):
        return True
    return intake.created_by == user.id


@router.get("/questions")
def get_questionnaire(user: User = Depends(get_current_user)):
    """پرسش‌های راهنمای تبدیل نیاز به مسئله — برای ویزارد فرانت."""
    return {"questions": questionnaire(), "algorithm_version": ALGORITHM_VERSION,
            "note": "خروجی دستیار پیش‌نویس و برآورد است؛ تأیید نهایی با کارشناس است"}


@router.post("/intakes")
def create_intake(payload: IntakeIn, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    require_roles(user, get_memberships(db, user), *ALLOWED)
    orgs = _my_industry_orgs(db, user)
    is_cio = ({m.role for m in get_memberships(db, user)} &
              {MemberRole.cio_manager, MemberRole.cio_expert})
    org_id = payload.organization_id
    if org_id and orgs and org_id not in orgs and not is_cio:
        raise HTTPException(status_code=403, detail={
            "code": "forbidden_org_scope", "message": "سازمان انتخابی متعلق به شما نیست"})
    if not org_id and orgs:
        org_id = orgs[0]   # پیش‌فرض: نخستین سازمان صنعتی خود کاربر
    if not org_id and not is_cio:
        raise HTTPException(status_code=403, detail={
            "code": "forbidden_org_scope",
            "message": "برای ساخت پیش‌نویس، سازمان صنعتی باید مشخص باشد"})
    draft = build_draft(payload.answers)
    intake = AssistantIntake(organization_id=org_id, created_by=user.id,
                             answers=payload.answers, draft=draft)
    db.add(intake)
    db.flush()
    log_audit(db, user.id, "assistant_intake_created", "assistant_intake", intake.id,
              {"confidence": draft["data_confidence"], "skills": draft["required_skills"]},
              request)
    db.commit()
    return {"id": intake.id, "status": intake.status, "draft": draft,
            "algorithm_version": ALGORITHM_VERSION}


@router.get("/intakes")
def list_intakes(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (db.query(AssistantIntake).filter_by(created_by=user.id)
            .order_by(AssistantIntake.created_at.desc()).limit(50).all())
    return {"items": [{"id": r.id, "status": r.status, "problem_id": r.problem_id,
                       "title": (r.draft or {}).get("title"),
                       "confidence": (r.draft or {}).get("data_confidence"),
                       "created_at": r.created_at.isoformat()} for r in rows]}


@router.get("/intakes/{intake_id}")
def get_intake(intake_id: str, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    r = db.get(AssistantIntake, intake_id)
    if not r or not _can_manage(db, user, r):
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message": "جلسه پرسش‌گری یافت نشد یا دسترسی ندارید"})
    return {"id": r.id, "status": r.status, "answers": r.answers, "draft": r.draft,
            "problem_id": r.problem_id, "created_at": r.created_at.isoformat()}


@router.post("/intakes/{intake_id}/confirm")
def confirm_intake(intake_id: str, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """تأیید انسانی پیش‌نویس ← ساخت مسئله واقعی در چرخهٔ عادی بررسی/انتشار."""
    r = db.get(AssistantIntake, intake_id)
    if not r or not _can_manage(db, user, r):
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message": "جلسه پرسش‌گری یافت نشد یا دسترسی ندارید"})
    if r.status != "draft":
        raise HTTPException(status_code=409, detail={
            "code": "already_confirmed", "message": "این پیش‌نویس قبلاً نهایی شده است"})
    d = r.draft or {}
    if not r.organization_id:
        raise HTTPException(status_code=422, detail={
            "code": "org_required",
            "message": "برای تبدیل پیش‌نویس به مسئله، سازمان صنعتی مالک باید مشخص باشد"})
    est = d.get("estimate") or {}
    p = IndustrialProblem(
        owner_organization_id=r.organization_id,
        title=d.get("title") or "مسئلهٔ پیشنهادی دستیار",
        summary=d.get("summary") or d.get("title") or "",
        description=(d.get("scope") or {}).get("problem_statement") or d.get("summary") or "",
        category=None,
        expected_outcomes=[d.get("deliverable")] if d.get("deliverable") else None,
        acceptance_criteria=d.get("acceptance_criteria") or None,
        duration_days=(est.get("duration_weeks") or 0) * 7 or None,
        budget_min=(est.get("budget_range_million_IRR") or [None, None])[0] * 1_000_000
        if est.get("budget_range_million_IRR") else None,
        budget_max=(est.get("budget_range_million_IRR") or [None, None])[1] * 1_000_000
        if est.get("budget_range_million_IRR") else None,
        budget_confirmed=False,   # برآورد دستیار — تا تأیید کارشناس قطعی نیست
        resources_offered=None,
        status=ProblemStatus.draft,
        created_by=user.id,
    )
    db.add(p)
    db.flush()
    from .problems import _snapshot_version, _upsert_skills
    _upsert_skills(db, p, d.get("required_skills") or [])
    _snapshot_version(db, p, user.id)
    r.status = "confirmed"
    r.problem_id = p.id
    r.confirmed_at = utcnow()
    log_audit(db, user.id, "assistant_intake_confirmed", "industrial_problem", p.id,
              {"intake_id": r.id, "algorithm": r.algorithm_version}, request)
    db.commit()
    return {"ok": True, "problem_id": p.id, "problem": problem_detail(p),
            "note": "مسئله در وضعیت پیش‌نویس ساخته شد؛ بودجه برآوردی است و پیش از انتشار کارشناس آن را نهایی می‌کند"}
