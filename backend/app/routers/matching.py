"""APIهای موتور تطبیق — اجرای رتبه‌بندی، نتایج با دلیل، پیشنهاد شخصی."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from ..core.deps import get_current_user, get_memberships, is_university_staff
from ..db import get_db
from ..models import (
    Application, CollaborationProject, IndustrialProblem, MatchRun, MemberRole,
    MatchResult, User, utcnow,
)
from ..serializers import problem_brief, user_brief
from ..services import log_audit
from ..services.matching import recommend_problems_for_user, run_matching

router = APIRouter(tags=["matching"])

INDUSTRY_ROLES = (MemberRole.industry_rep, MemberRole.industry_manager)


@router.post("/problems/{problem_id}/match-runs")
def create_match_run(problem_id: str, request: Request, db: Session = Depends(get_db),
                     user: User = Depends(get_current_user)):
    p = db.get(IndustrialProblem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "مسئله یافت نشد"})
    memberships = get_memberships(db, user)
    allowed = (any(m.organization_id == p.owner_organization_id and m.role in INDUSTRY_ROLES
                   for m in memberships) or
               ({m.role for m in memberships} & {MemberRole.cio_manager, MemberRole.cio_expert}))
    if not allowed:
        raise HTTPException(status_code=403, detail={
            "code": "forbidden", "message": "اجرای تطبیق فقط برای سازمان مالک یا دفتر ارتباط با صنعت مجاز است"})
    run = run_matching(db, p, user.id)
    log_audit(db, user.id, "match_run_executed", "industrial_problem", p.id,
              {"run_id": run.id, "algorithm": run.algorithm_version}, request)
    db.commit()
    return {"id": run.id, "algorithm_version": run.algorithm_version,
            "status": run.status.value if hasattr(run.status, "value") else run.status,
            "stats": run.stats}


@router.get("/match-runs/{run_id}")
def get_match_run(run_id: str, db: Session = Depends(get_db),
                  user: User = Depends(get_current_user)):
    run = db.get(MatchRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "اجرای تطبیق یافت نشد"})
    return {"id": run.id, "problem_id": run.problem_id,
            "algorithm_version": run.algorithm_version,
            "status": run.status.value if hasattr(run.status, "value") else run.status,
            "weights": run.weights, "stats": run.stats,
            "created_at": run.created_at.isoformat()}


@router.get("/match-runs/{run_id}/results")
def get_match_results(run_id: str, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    run = db.get(MatchRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "اجرای تطبیق یافت نشد"})
    p = db.get(IndustrialProblem, run.problem_id)
    memberships = get_memberships(db, user)
    allowed = (any(m.organization_id == p.owner_organization_id and m.role in INDUSTRY_ROLES
                   for m in memberships) or is_university_staff(memberships))
    if not allowed:
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                     "message": "دسترسی به نتایج تطبیق غیرمجاز است"})
    results = db.query(MatchResult).filter_by(match_run_id=run_id).order_by(MatchResult.rank).all()
    items = []
    for r in results:
        u = db.get(User, r.user_id)
        # پروفایل حداقلی/ناشناس پیش از انتخاب — تا زمان اعلام رضایت
        items.append({
            "rank": r.rank, "score": r.score,
            "user": user_brief(u, full_access=False),
            "reasons": r.reasons, "missing": r.missing,
            "data_quality_note": r.data_quality_note,
        })
    return {"items": items, "total": len(items),
            "algorithm_version": run.algorithm_version, "weights": run.weights}


@router.get("/me/recommended-problems")
def my_recommended_problems(db: Session = Depends(get_db),
                            user: User = Depends(get_current_user)):
    if user.user_type not in ("student", "professor"):
        return {"items": [], "note": "پیشنهاد مسئله فقط برای دانشجو و استاد فعال است"}
    items = recommend_problems_for_user(db, user)
    return {"items": items, "total": len(items),
            "note": "پیشنهاد سامانه است؛ تصمیم نهایی با شما و مسئولان است"}


# ---------- تیم‌سازی توضیح‌پذیر (v1.1.0) ----------

@router.post("/problems/{problem_id}/team-proposals")
def create_team_proposal(problem_id: str, request: Request, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    """ترکیب پیشنهادی تیم (استاد راهبر + متخصص + مکمل + منابع) با دو شاخص جدای fit/confidence."""
    from ..models import TeamProposal
    from ..serializers import problem_detail
    from ..services.team import build_team_proposal

    p = db.get(IndustrialProblem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "مسئله یافت نشد"})
    memberships = get_memberships(db, user)
    allowed = (any(m.organization_id == p.owner_organization_id and m.role in INDUSTRY_ROLES
                   for m in memberships) or
               ({m.role for m in memberships} & {MemberRole.cio_manager, MemberRole.cio_expert}))
    if not allowed:
        raise HTTPException(status_code=403, detail={
            "code": "forbidden",
            "message": "پیشنهاد تیم فقط برای سازمان مالک یا دفتر ارتباط با صنعت مجاز است"})
    built = build_team_proposal(db, p, user.id)
    tp = TeamProposal(problem_id=p.id, algorithm_version=built["algorithm_version"],
                     composition=built["composition"], coverage=built["coverage"],
                     explanation=built["explanation"], resource_notes=built["resource_notes"],
                     created_by=user.id)
    db.add(tp)
    db.flush()
    log_audit(db, user.id, "team_proposal_created", "industrial_problem", p.id,
              {"proposal_id": tp.id, "algorithm": tp.algorithm_version}, request)
    db.commit()
    return {"id": tp.id, "status": tp.status, "composition": tp.composition,
            "coverage": tp.coverage, "explanation": tp.explanation,
            "resource_notes": tp.resource_notes,
            "candidates_evaluated": built["candidates_evaluated"],
            "human_decision_required": True}


@router.get("/problems/{problem_id}/team-proposals")
def list_team_proposals(problem_id: str, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    from ..models import TeamProposal
    p = db.get(IndustrialProblem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "مسئله یافت نشد"})
    memberships = get_memberships(db, user)
    allowed = (any(m.organization_id == p.owner_organization_id and m.role in INDUSTRY_ROLES
                   for m in memberships) or
               ({m.role for m in memberships} &
                {MemberRole.cio_manager, MemberRole.cio_expert,
                 MemberRole.professor, MemberRole.university_admin}))
    if not allowed:
        raise HTTPException(status_code=403, detail={
            "code": "forbidden", "message": "دسترسی غیرمجاز"})
    rows = (db.query(TeamProposal).filter_by(problem_id=problem_id)
            .order_by(TeamProposal.created_at.desc()).limit(20).all())
    return {"items": [{"id": r.id, "status": r.status,
                       "algorithm_version": r.algorithm_version,
                       "composition": r.composition, "coverage": r.coverage,
                       "explanation": r.explanation, "resource_notes": r.resource_notes,
                       "project_id": r.project_id,
                       "created_at": r.created_at.isoformat()} for r in rows]}


@router.post("/team-proposals/{proposal_id}/accept")
def accept_team_proposal(proposal_id: str, request: Request, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    """پذیرش پیشنهاد تیم (تصمیم انسانی) ← ساخت همکاری با اعضای پیشنهادی."""
    from ..models import ProjectMember, TeamProposal
    tp = db.get(TeamProposal, proposal_id)
    if not tp:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message": "پیشنهاد تیم یافت نشد"})
    p = db.get(IndustrialProblem, tp.problem_id)
    memberships = get_memberships(db, user)
    allowed = (any(m.organization_id == p.owner_organization_id and m.role in INDUSTRY_ROLES
                   for m in memberships) or
               ({m.role for m in memberships} & {MemberRole.cio_manager, MemberRole.cio_expert}))
    if not allowed:
        raise HTTPException(status_code=403, detail={
            "code": "forbidden", "message": "پذیرش تیم فقط برای سازمان مالک یا دفتر ارتباط مجاز است"})
    if tp.status != "proposed":
        raise HTTPException(status_code=409, detail={
            "code": "already_decided", "message": "این پیشنهاد قبلاً تصمیم‌گیری شده است"})

    from ..models import ProjectStatus
    prof = next((m for m in tp.composition if m["role_in_team"] == "استاد راهبر"), None)
    if not prof:
        raise HTTPException(status_code=422, detail={
            "code": "no_leader", "message": "پیشنهاد بدون استاد راهبر قابل پذیرش نیست"})
    prof_user = db.get(User, prof["user"]["id"])
    prof_org = next((m.organization_id for m in get_memberships(db, prof_user)
                     if m.role == MemberRole.professor), None)
    uni_org = prof_org or next(
        (m.organization_id for m in memberships if m.organization.org_type.value == "university"), None)
    from ..models import Organization
    if not uni_org:
        uni = db.query(Organization).filter_by(org_type="university").first()
        uni_org = uni.id if uni else None
    if not uni_org:
        raise HTTPException(status_code=422, detail={
            "code": "no_university", "message": "سازمان دانشگاهی برای تشکیل تیم یافت نشد"})

    proj = CollaborationProject(
        problem_id=p.id, title=f"تیم پیشنهادی — {p.title}",
        scope=(tp.explanation or "")[:400],
        acceptance_summary="؛ ".join(p.acceptance_criteria or []) or None,
        industry_org_id=p.owner_organization_id, university_org_id=uni_org,
        academic_lead_user_id=prof_user.id, industry_rep_user_id=user.id,
        status=ProjectStatus.proposed,
        status_note="ساخته‌شده از پیشنهاد تیم‌سازی توضیح‌پذیر؛ نیازمند تأیید قرارداد/پایلوت",
        created_by=user.id)
    db.add(proj)
    db.flush()
    db.add(ProjectMember(project_id=proj.id, user_id=prof_user.id,
                         organization_id=uni_org, role="استاد راهبر"))
    for m in tp.composition:
        if m["role_in_team"] in ("دانشجوی متخصص", "دانشجوی مکمل"):
            db.add(ProjectMember(project_id=proj.id, user_id=m["user"]["id"],
                                 organization_id=uni_org, role=m["role_in_team"]))
    tp.status = "accepted"
    tp.decided_by = user.id
    tp.decided_at = utcnow()
    tp.project_id = proj.id
    log_audit(db, user.id, "team_proposal_accepted", "collaboration_project", proj.id,
              {"proposal_id": tp.id, "members": len(tp.composition)}, request)
    db.commit()
    return {"ok": True, "project_id": proj.id,
            "note": "همکاری در وضعیت «پیشنهاد» ساخته شد؛ گام بعدی پایلوت یا قرارداد است"}
