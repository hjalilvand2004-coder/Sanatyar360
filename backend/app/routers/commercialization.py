"""غربالگری فرصت تجاری‌سازی — ابزار کمک به تصمیم؛ نه مرجع قطعی ارزش‌گذاری (AC-12)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, get_memberships
from ..db import get_db
from ..models import (
    CommercializationCase, CommercializationReview, CommCaseStatus,
    MemberRole, OrganizationMembership, ResearchAssetSnapshot, User,
)
from ..services import log_audit, notify

router = APIRouter(tags=["commercialization"])

COMM_EXPERT = {MemberRole.comm_expert, MemberRole.cio_manager}


class ResearchAssetIn(BaseModel):
    external_research_id: str | None = None
    title: str = Field(min_length=5, max_length=250)
    asset_type: str = Field(default="paper", pattern="^(paper|patent|prototype)$")
    summary: str | None = None
    trl_level: int | None = Field(default=None, ge=1, le=9)
    application_fields: list[str] = []
    evidence: list[dict] = []
    ip_status: str | None = None


class CaseIn(BaseModel):
    title: str = Field(min_length=5, max_length=250)
    rationale: str = Field(min_length=20)
    research_asset_id: str | None = None
    related_problem_id: str | None = None
    application_fields: list[str] = []
    # هر ادعا باید به منبع متصل شود: {claim, source, kind: explicit|inference}
    evidence: list[dict] = []
    uncertainties: str | None = None
    market_signal: str | None = None


class ReviewIn(BaseModel):
    need_fit_score: int | None = Field(default=None, ge=1, le=5)
    trl_assessment: int | None = Field(default=None, ge=1, le=9)
    market_evidence_score: int | None = Field(default=None, ge=1, le=5)
    comment: str | None = None
    next_action: str | None = None
    decision: str = Field(pattern="^(proceed|reject|need_info)$")


@router.post("/commercialization/research-assets")
def create_research_asset(payload: ResearchAssetIn, request: Request,
                          db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    asset = ResearchAssetSnapshot(**payload.model_dump(), owner_user_id=user.id)
    db.add(asset)
    db.commit()
    return {"id": asset.id}


@router.get("/commercialization/cases")
def list_cases(status: str | None = None, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    query = db.query(CommercializationCase)
    if status:
        query = query.filter(CommercializationCase.status == status)
    cases = query.order_by(CommercializationCase.created_at.desc()).limit(200).all()
    return {"items": [_case_dict(db, c) for c in cases], "total": len(cases)}


@router.post("/commercialization/cases")
def create_case(payload: CaseIn, request: Request, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    memberships = get_memberships(db, user)
    roles = {m.role for m in memberships}
    if not (roles & {MemberRole.cio_manager, MemberRole.cio_expert, MemberRole.comm_expert,
                     MemberRole.professor, MemberRole.sys_admin}):
        raise HTTPException(status_code=403, detail={
            "code": "forbidden", "message": "ایجاد پرونده فرصت برای نقش شما مجاز نیست"})
    # تفکیک استنباط از اطلاعات صریح در شواهد
    for ev in payload.evidence:
        ev.setdefault("kind", "inference" if "source" not in ev else "explicit")
    case = CommercializationCase(**payload.model_dump(), created_by=user.id,
                                 status=CommCaseStatus.suggested)
    db.add(case)
    db.flush()
    experts = (db.query(User).join(OrganizationMembership,
                                   OrganizationMembership.user_id == User.id)
               .filter(OrganizationMembership.role == MemberRole.comm_expert,
                       OrganizationMembership.status == "active").all())
    for e in experts:
        notify(db, e.id, "پرونده فرصت تجاری‌سازی جدید",
               f"«{case.title}» برای ارزیابی تخصصی ثبت شد.", f"/commercialization/{case.id}")
    log_audit(db, user.id, "commercialization_case_created", "commercialization_case",
              case.id, {"title": case.title}, request)
    db.commit()
    return _case_dict(db, case)


def _case_dict(db: Session, c: CommercializationCase) -> dict:
    return {
        "id": c.id,
        "title": c.title,
        "rationale": c.rationale,
        "application_fields": c.application_fields,
        "evidence": c.evidence,
        "uncertainties": c.uncertainties,
        "market_signal": c.market_signal,
        "status": c.status.value if hasattr(c.status, "value") else c.status,
        "next_action": c.next_action,
        "research_asset_id": c.research_asset_id,
        "related_problem_id": c.related_problem_id,
        "created_at": c.created_at.isoformat(),
        "created_by": c.created_by,
        "reviews": [{
            "expert": (db.get(User, r.expert_user_id).full_name if db.get(User, r.expert_user_id) else "—"),
            "decision": r.decision, "need_fit_score": r.need_fit_score,
            "trl_assessment": r.trl_assessment, "market_evidence_score": r.market_evidence_score,
            "comment": r.comment, "next_action": r.next_action,
            "created_at": r.created_at.isoformat(),
        } for r in db.query(CommercializationReview).filter_by(case_id=c.id).all()],
        "note": "پیشنهاد سامانه/کارشناس بدون نظر متخصص تجاری‌سازی، نتیجه قطعی تلقی نمی‌شود",
    }


@router.get("/commercialization/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    c = db.get(CommercializationCase, case_id)
    if not c:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "پرونده یافت نشد"})
    return _case_dict(db, c)


@router.post("/commercialization/cases/{case_id}/reviews")
def review_case(case_id: str, payload: ReviewIn, request: Request,
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    memberships = get_memberships(db, user)
    if not ({m.role for m in memberships} & COMM_EXPERT):
        raise HTTPException(status_code=403, detail={
            "code": "forbidden",
            "message": "ارزیابی تخصصی فقط توسط کارشناس تجاری‌سازی ثبت می‌شود"})
    c = db.get(CommercializationCase, case_id)
    if not c:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "پرونده یافت نشد"})
    db.add(CommercializationReview(case_id=c.id, expert_user_id=user.id,
                                   **payload.model_dump(exclude={"decision"}) | {"decision": payload.decision}))
    if payload.decision == "proceed":
        c.status = CommCaseStatus.expert_approved
    elif payload.decision == "reject":
        c.status = CommCaseStatus.rejected
    elif payload.decision == "need_info":
        c.status = CommCaseStatus.under_expert_review
    c.next_action = payload.next_action
    log_audit(db, user.id, f"commercialization_review_{payload.decision}",
              "commercialization_case", c.id, request=request)
    notify(db, c.created_by, "ارزیابی تخصصی فرصت تجاری‌سازی ثبت شد",
           f"«{c.title}» → {payload.decision}", f"/commercialization/{c.id}")
    db.commit()
    return {"status": c.status.value}
