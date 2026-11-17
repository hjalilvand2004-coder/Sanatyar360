"""APIهای موتور تطبیق — اجرای رتبه‌بندی، نتایج با دلیل، پیشنهاد شخصی."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from ..core.deps import get_current_user, get_memberships, is_university_staff
from ..db import get_db
from ..models import (
    Application, IndustrialProblem, MatchRun, MemberRole, MatchResult, User,
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
