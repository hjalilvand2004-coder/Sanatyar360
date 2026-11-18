"""ثبت و پیگیری همکاری صنعتی — پروژه همکاری مستقل از مسئله و درخواست."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, get_memberships, is_university_staff
from ..db import get_db
from ..models import (
    AgreementReference, AppStatus, Application, ApplicationMember,
    CollaborationEvaluation, CollaborationProject, Deliverable, DeliverableStatus,
    IndustrialProblem, MemberRole, MilestoneStatus, Organization,
    OrganizationMembership, OrgType, ProblemStatus, ProjectMember,
    ProjectMilestone, ProjectStatus, User, utcnow,
)
from ..serializers import project_brief, user_brief
from ..services import add_outbox, log_audit, notify

router = APIRouter(tags=["collaborations"])

INDUSTRY_ROLES = (MemberRole.industry_rep, MemberRole.industry_manager)
CIO_ROLES = (MemberRole.cio_manager, MemberRole.cio_expert)


def _serialize_project(db: Session, p: CollaborationProject, user: User,
                       memberships) -> dict:
    industry_org = db.get(Organization, p.industry_org_id)
    university_org = db.get(Organization, p.university_org_id)
    lead = db.get(User, p.academic_lead_user_id)
    rep = db.get(User, p.industry_rep_user_id)
    d = project_brief(p)
    d.update({
        "industry_org": {"id": industry_org.id, "name": industry_org.name} if industry_org else None,
        "university_org": {"id": university_org.id, "name": university_org.name} if university_org else None,
        "academic_lead": user_brief(lead) if lead else None,
        "industry_rep": user_brief(rep) if rep else None,
        "milestones": [{"id": m.id, "title": m.title, "due_date": m.due_date,
                        "status": m.status.value} for m in db.query(ProjectMilestone)
                       .filter_by(project_id=p.id).order_by(ProjectMilestone.created_at).all()],
        "deliverables": [{"id": dv.id, "title": dv.title, "description": dv.description,
                          "status": dv.status.value, "review_note": dv.review_note,
                          "submitted_at": dv.submitted_at.isoformat(),
                          "reviewed_at": dv.reviewed_at.isoformat() if dv.reviewed_at else None}
                         for dv in db.query(Deliverable).filter_by(project_id=p.id)
                         .order_by(Deliverable.submitted_at.desc()).all()],
        "members": [{"user": user_brief(m.user), "role": m.role}
                    for m in db.query(ProjectMember).filter_by(project_id=p.id).all()],
        "evaluations": [{"rating": e.rating, "comment": e.comment,
                         "created_at": e.created_at.isoformat()}
                        for e in db.query(CollaborationEvaluation).filter_by(project_id=p.id).all()],
        "agreements": [{"ref_type": r.ref_type, "reference_code": r.reference_code,
                        "note": r.note} for r in db.query(AgreementReference)
                       .filter_by(project_id=p.id).all()],
        "problem_title": (db.get(IndustrialProblem, p.problem_id).title
                          if p.problem_id else None),
    })
    d["my_roles"] = [m.role.value for m in memberships]
    return d


class CollaborationIn(BaseModel):
    problem_id: str
    application_id: str
    title: str | None = Field(default=None, max_length=250)
    scope: str | None = None
    acceptance_summary: str | None = None
    agreement_ref: str | None = None
    nda_ref: str | None = None
    milestones: list[dict] = []


@router.post("/collaborations")
def create_collaboration(payload: CollaborationIn, request: Request,
                         db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    memberships = get_memberships(db, user)
    app = db.get(Application, payload.application_id)
    if not app:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "درخواست همکاری یافت نشد"})
    if app.status != AppStatus.accepted:
        raise HTTPException(status_code=409, detail={
            "code": "invalid_state",
            "message": "ایجاد همکاری فقط از درخواست «پذیرفته‌شده» ممکن است (AC-08)"})
    p = db.get(IndustrialProblem, payload.problem_id)
    if not p or app.problem_id != p.id:
        raise HTTPException(status_code=422, detail={
            "code": "mismatch", "message": "مسئله و درخواست هم‌خوان نیستند"})
    is_owner_rep = any(m.organization_id == p.owner_organization_id and m.role in INDUSTRY_ROLES
                       for m in memberships)
    is_cio = {m.role for m in memberships} & set(CIO_ROLES)
    if not (is_owner_rep or is_cio):
        raise HTTPException(status_code=403, detail={
            "code": "forbidden",
            "message": "ایجاد همکاری توسط نماینده صنعت مالک یا دفتر ارتباط با صنعت انجام می‌شود"})
    dup = db.query(CollaborationProject).filter_by(application_id=app.id).first()
    if dup:
        raise HTTPException(status_code=409, detail={
            "code": "duplicate", "message": "برای این درخواست قبلاً پروژه همکاری ایجاد شده است"})
    applicant = db.get(User, app.applicant_user_id)
    lead = applicant if applicant.user_type == "professor" else None
    # مسئول علمی باید استاد باشد؛ در غیر این صورت از اعضای تیم استاد انتخاب می‌شود
    if lead is None:
        for m in db.query(ApplicationMember).filter_by(application_id=app.id,
                                                       status="accepted").all():
            mu = db.get(User, m.user_id)
            if mu and mu.user_type == "professor":
                lead = mu
                break
    uni_org_id = None
    for cand in ([lead.id if lead else None, applicant.id]):
        if cand and uni_org_id is None:
            pm = (db.query(OrganizationMembership)
                  .filter(OrganizationMembership.user_id == cand,
                          OrganizationMembership.status == "active").all())
            for m in pm:
                org = db.get(Organization, m.organization_id)
                if org and org.org_type == OrgType.university:
                    uni_org_id = org.id
                    break
    if uni_org_id is None:
        raise HTTPException(status_code=422, detail={
            "code": "university_missing",
            "message": "دانشگاه طرف دانشگاهی همکاری مشخص نیست؛ متقاضی باید عضو یک دانشگاه باشد"})
    proj = CollaborationProject(
        problem_id=p.id, application_id=app.id,
        title=payload.title or f"همکاری صنعتی: {p.title}",
        scope=payload.scope or p.summary,
        acceptance_summary=payload.acceptance_summary or "؛ ".join(p.acceptance_criteria or []) or None,
        industry_org_id=p.owner_organization_id,
        university_org_id=uni_org_id,
        academic_lead_user_id=(lead.id if lead else applicant.id),
        industry_rep_user_id=p.created_by,
        agreement_ref=payload.agreement_ref, nda_ref=payload.nda_ref,
        status=ProjectStatus.agreement_pending, created_by=user.id)
    db.add(proj)
    db.flush()
    db.add(ProjectMember(project_id=proj.id, user_id=applicant.id,
                         organization_id=p.owner_organization_id, role="متقاضی اصلی"))
    if lead:
        db.add(ProjectMember(project_id=proj.id, user_id=lead.id,
                             organization_id=proj.university_org_id, role="مسئول علمی"))
    db.add(ProjectMember(project_id=proj.id, user_id=p.created_by,
                         organization_id=p.owner_organization_id, role="نماینده صنعت"))
    for m in db.query(ApplicationMember).filter_by(application_id=app.id,
                                                   status="accepted").all():
        db.add(ProjectMember(project_id=proj.id, user_id=m.user_id,
                             role=m.role or "عضو تیم"))
    for i, ms in enumerate(payload.milestones[:20]):
        db.add(ProjectMilestone(project_id=proj.id, title=ms.get("title", f"نقطه عطف {i+1}"),
                                due_date=ms.get("due_date")))
    if payload.agreement_ref:
        db.add(AgreementReference(project_id=proj.id, ref_type="contract",
                                  reference_code=payload.agreement_ref))
    if payload.nda_ref:
        db.add(AgreementReference(project_id=proj.id, ref_type="nda", reference_code=payload.nda_ref))
    # حفظ اطلاعات مبنا: مسئله → وضعیت تبدیل (اگر سیاست دانشگاه اجازه چند همکاری بدهد، تکراری می‌سازد)
    p.status = ProblemStatus.converted_to_project
    add_outbox(db, "collaboration.created",
               {"project_code": proj.code, "problem_id": p.id, "application_id": app.id},
               dedupe_key=f"collab.created:{proj.code}")
    log_audit(db, user.id, "collaboration_created", "collaboration_project", proj.id,
              {"problem_id": p.id, "application_id": app.id}, request)
    for pm in db.query(ProjectMember).filter_by(project_id=proj.id).all():
        notify(db, pm.user_id, "پروژه همکاری شکل گرفت",
               f"پروژه «{proj.title}» با کد {proj.code} ایجاد شد.", f"/collaborations/{proj.id}")
    db.commit()
    return _serialize_project(db, proj, user, memberships)


@router.get("/collaborations")
def list_collaborations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    memberships = get_memberships(db, user)
    my_ids = {m.organization_id for m in memberships}
    projects = db.query(CollaborationProject).order_by(
        CollaborationProject.created_at.desc()).all()
    items = []
    for p in projects:
        if is_university_staff(memberships) or p.industry_org_id in my_ids or p.university_org_id in my_ids:
            items.append(project_brief(p))
    return {"items": items, "total": len(items)}


@router.get("/collaborations/{proj_id}")
def get_collaboration(proj_id: str, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    p = db.get(CollaborationProject, proj_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "پروژه همکاری یافت نشد"})
    memberships = get_memberships(db, user)
    my_ids = {m.organization_id for m in memberships}
    involved = db.query(ProjectMember).filter_by(project_id=p.id, user_id=user.id).first()
    if not (is_university_staff(memberships) or p.industry_org_id in my_ids or
            p.university_org_id in my_ids or involved):
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                     "message": "دسترسی غیرمجاز به این همکاری"})
    return _serialize_project(db, p, user, memberships)


class MilestoneIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    due_date: str | None = None


@router.post("/collaborations/{proj_id}/milestones")
def add_milestone(proj_id: str, payload: MilestoneIn, request: Request,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = db.get(CollaborationProject, proj_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "پروژه یافت نشد"})
    memberships = get_memberships(db, user)
    my_ids = {m.organization_id for m in memberships}
    if not (p.industry_org_id in my_ids or p.university_org_id in my_ids or
            is_university_staff(memberships)):
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                     "message": "دسترسی غیرمجاز"})
    m = ProjectMilestone(project_id=p.id, title=payload.title, due_date=payload.due_date)
    db.add(m)
    log_audit(db, user.id, "milestone_added", "collaboration_project", p.id,
              {"title": payload.title}, request)
    db.commit()
    return {"id": m.id, "status": m.status.value}


class StatusIn(BaseModel):
    status: ProjectStatus
    note: str | None = None
    final_achievement: str | None = None


ALLOWED_TRANSITIONS = {
    ProjectStatus.proposed: {ProjectStatus.agreement_pending, ProjectStatus.terminated},
    ProjectStatus.agreement_pending: {ProjectStatus.active, ProjectStatus.terminated, ProjectStatus.proposed},
    ProjectStatus.active: {ProjectStatus.on_hold, ProjectStatus.completed, ProjectStatus.terminated},
    ProjectStatus.on_hold: {ProjectStatus.active, ProjectStatus.terminated, ProjectStatus.completed},
    ProjectStatus.completed: set(),
    ProjectStatus.terminated: set(),
}


@router.post("/collaborations/{proj_id}/status")
def change_status(proj_id: str, payload: StatusIn, request: Request,
                  db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = db.get(CollaborationProject, proj_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "پروژه یافت نشد"})
    memberships = get_memberships(db, user)
    is_owner_rep = any(m.organization_id == p.industry_org_id and m.role in INDUSTRY_ROLES
                       for m in memberships)
    is_cio = {m.role for m in memberships} & set(CIO_ROLES)
    is_lead = user.id == p.academic_lead_user_id
    if not (is_owner_rep or is_cio or is_lead):
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                     "message": "تغییر وضعیت فقط توسط طرف‌های همکاری مجاز است"})
    if payload.status not in ALLOWED_TRANSITIONS.get(p.status, set()):
        raise HTTPException(status_code=409, detail={
            "code": "invalid_transition",
            "message": f"گذار از «{p.status.value}» به «{payload.status.value}» مجاز نیست"})
    if payload.status == ProjectStatus.completed and not (payload.final_achievement or
                                                          p.final_achievement):
        raise HTTPException(status_code=422, detail={
            "code": "achievement_required",
            "message": "برای تکمیل همکاری، ثبت دستاورد نهایی الزامی است"})
    if payload.status == ProjectStatus.terminated and not payload.note:
        raise HTTPException(status_code=422, detail={"code": "note_required",
                                                     "message": "ثبت دلیل خاتمه الزامی است"})
    p.status = payload.status
    p.status_note = payload.note
    if payload.final_achievement:
        p.final_achievement = payload.final_achievement
    if payload.status == ProjectStatus.active and not p.started_at:
        p.started_at = utcnow()
        if not p.agreement_ref:
            p.status_note = (payload.note or "") + " (هشدار: قرارداد ثبت‌شده ندارد)"
    if payload.status == ProjectStatus.completed:
        p.completed_at = utcnow()
    log_audit(db, user.id, f"project_status_{payload.status.value}", "collaboration_project",
              p.id, {"note": payload.note}, request)
    for pm in db.query(ProjectMember).filter_by(project_id=p.id).all():
        notify(db, pm.user_id, "وضعیت پروژه همکاری تغییر کرد",
               f"«{p.title}» → {payload.status.value}", f"/collaborations/{p.id}")
    db.commit()
    return {"status": p.status.value, "started_at": p.started_at.isoformat() if p.started_at else None}


class DeliverableIn(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = None
    milestone_id: str | None = None


@router.post("/collaborations/{proj_id}/deliverables")
def submit_deliverable(proj_id: str, payload: DeliverableIn, request: Request,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = db.get(CollaborationProject, proj_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "پروژه یافت نشد"})
    involved = db.query(ProjectMember).filter_by(project_id=p.id, user_id=user.id).first()
    memberships = get_memberships(db, user)
    is_academic = (involved and user.user_type in ("student", "professor")) or \
                  p.university_org_id in {m.organization_id for m in memberships}
    if p.status not in (ProjectStatus.active, ProjectStatus.on_hold):
        raise HTTPException(status_code=409, detail={"code": "invalid_state",
                                                     "message": "ثبت خروجی فقط در پروژه فعال/متوقف مجاز است"})
    if not is_academic:
        raise HTTPException(status_code=403, detail={
            "code": "forbidden", "message": "ثبت خروجی بر عهده طرف دانشگاهی است"})
    d = Deliverable(project_id=p.id, title=payload.title, description=payload.description,
                    milestone_id=payload.milestone_id, submitted_by=user.id,
                    status=DeliverableStatus.submitted)
    db.add(d)
    log_audit(db, user.id, "deliverable_submitted", "collaboration_project", p.id,
              {"title": payload.title}, request)
    notify(db, p.industry_rep_user_id, "خروجی جدید ثبت شد",
           f"خروجی «{payload.title}» برای پروژه «{p.title}» ثبت شد و در انتظار پذیرش است.",
           f"/collaborations/{p.id}")
    db.commit()
    return {"id": d.id, "status": d.status.value}


class DeliverableReviewIn(BaseModel):
    decision: str = Field(pattern="^(accept|revision_requested)$")
    note: str | None = None


@router.post("/deliverables/{deliv_id}/reviews")
def review_deliverable(deliv_id: str, payload: DeliverableReviewIn, request: Request,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    d = db.get(Deliverable, deliv_id)
    if not d:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "خروجی یافت نشد"})
    p = db.get(CollaborationProject, d.project_id)
    memberships = get_memberships(db, user)
    # AC-09: پذیرش خروجی فقط توسط نقش مجاز (نماینده صنعت مالک)
    is_owner_rep = any(m.organization_id == p.industry_org_id and m.role in INDUSTRY_ROLES
                       for m in memberships)
    if not is_owner_rep:
        raise HTTPException(status_code=403, detail={
            "code": "forbidden", "message": "پذیرش خروجی فقط توسط نماینده صنعت انجام می‌شود"})
    if d.status != DeliverableStatus.submitted:
        raise HTTPException(status_code=409, detail={"code": "invalid_state",
                                                     "message": "این خروجی قبلاً بررسی شده است"})
    d.status = DeliverableStatus.accepted if payload.decision == "accept" else \
        DeliverableStatus.revision_requested
    d.review_note = payload.note
    d.reviewed_by = user.id
    d.reviewed_at = utcnow()
    if payload.decision == "accept" and d.milestone_id:
        m = db.get(ProjectMilestone, d.milestone_id)
        if m:
            m.status = MilestoneStatus.done
            m.completed_at = utcnow()
    log_audit(db, user.id, f"deliverable_{payload.decision}", "deliverable", d.id,
              {"note": payload.note}, request)
    notify(db, d.submitted_by, "بررسی خروجی ثبت شد",
           f"خروجی «{d.title}» → {d.status.value}" + (f" | {payload.note}" if payload.note else ""),
           f"/collaborations/{p.id}")
    db.commit()
    return {"status": d.status.value}


class EvaluationIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


@router.post("/collaborations/{proj_id}/evaluations")
def evaluate_collaboration(proj_id: str, payload: EvaluationIn, request: Request,
                           db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = db.get(CollaborationProject, proj_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "پروژه یافت نشد"})
    memberships = get_memberships(db, user)
    my_ids = {m.organization_id for m in memberships}
    involved = db.query(ProjectMember).filter_by(project_id=p.id, user_id=user.id).first()
    if not (p.industry_org_id in my_ids or p.university_org_id in my_ids or involved):
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                     "message": "ارزیابی فقط توسط طرف‌های همکاری"})
    dup = db.query(CollaborationEvaluation).filter_by(project_id=p.id,
                                                      evaluator_user_id=user.id).first()
    if dup:
        raise HTTPException(status_code=409, detail={"code": "duplicate",
                                                     "message": "شما قبلاً این همکاری را ارزیابی کرده‌اید"})
    db.add(CollaborationEvaluation(project_id=p.id, evaluator_user_id=user.id,
                                   rating=payload.rating, comment=payload.comment))
    log_audit(db, user.id, "collaboration_evaluated", "collaboration_project", p.id,
              {"rating": payload.rating}, request)
    db.commit()
    return {"ok": True}


class AchievementIn(BaseModel):
    final_achievement: str = Field(min_length=10)


@router.patch("/collaborations/{proj_id}/achievement")
def update_achievement(proj_id: str, payload: AchievementIn, request: Request,
                       db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    p = db.get(CollaborationProject, proj_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "پروژه یافت نشد"})
    memberships = get_memberships(db, user)
    my_ids = {m.organization_id for m in memberships}
    if not (p.industry_org_id in my_ids or p.university_org_id in my_ids or
            is_university_staff(memberships) or
            db.query(ProjectMember).filter_by(project_id=p.id, user_id=user.id).first()):
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                     "message": "دسترسی غیرمجاز"})
    p.final_achievement = payload.final_achievement
    log_audit(db, user.id, "achievement_updated", "collaboration_project", p.id, request=request)
    db.commit()
    return {"ok": True}
