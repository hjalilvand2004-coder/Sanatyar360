"""موتور تطبیق قواعدی — نسخه‌دار و با ثبت دلیل (AC-06).

امتیاز = شایستگی + تجربه مرتبط + تناسب شرایط اجرا.
این امتیاز احتمال موفقیت نیست؛ صرفاً رتبه‌بندی کمکی است و انتخاب نهایی انسانی است.
"""
from sqlalchemy.orm import Session

from ..models import (
    IndustrialProblem, MaharatLink, MatchResult, MatchRun, MatchRunStatus, MemberRole,
    MembershipStatus, OrganizationMembership, User, UserSkillSnapshot, utcnow, WorkMode,
)
from .maharat import matching_boost as maharat_boost

ALGORITHM_VERSION = "rules-v1.0"
WEIGHTS = {"skill_fit": 0.45, "evidence": 0.25, "profile_fit": 0.15, "conditions_fit": 0.15}


def _maharat_boost(db: Session, problem, user_id: str) -> dict:
    """عامل مهارت‌یار۳۶۰ — فقط برای کاربرانِ دارای پیوند معتبر؛ در قطعی، بی‌اثر."""
    try:
        link = db.query(MaharatLink).filter_by(user_id=user_id).first()
        return maharat_boost(problem, link)
    except Exception:
        return {}


def _skill_map(db: Session, user_id: str) -> dict[str, dict]:
    rows = db.query(UserSkillSnapshot).filter(UserSkillSnapshot.user_id == user_id).all()
    return {r.skill_id: {"level": r.level, "source": r.source, "skill_name": r.skill.name}
            for r in rows}


def score_candidate(db: Session, problem: IndustrialProblem, user: User) -> dict | None:
    """None = candidate was filtered out by hard requirements."""
    reasons, missing = [], []

    # مرحله اول — فیلتر شرایط الزامی (قبل از رتبه‌بندی)
    if user.user_type not in ("student", "professor"):
        return None
    if problem.owner_organization_id in (
            m.organization_id for m in db.query(OrganizationMembership)
            .filter(OrganizationMembership.user_id == user.id,
                    OrganizationMembership.status == MembershipStatus.active).all()):
        return None  # نماینده همان سازمان
    if problem.nda_required:
        reasons.append("نیازمند پذیرش NDA پیش از دسترسی به جزئیات محرمانه")

    required = {rs.skill_id: rs for rs in problem.required_skills if rs.is_required}
    smap = _skill_map(db, user.id)

    # مهارت‌های تأییدشده مهارت‌یار۳۶۰ هم در پوشش الزامی‌ها شمرده می‌شوند
    boost = _maharat_boost(db, problem, user.id)
    covered_names = set((boost or {}).get("covered_skills", {}))
    maharat_only = [rs for rs in required.values()
                    if rs.skill.name in covered_names and rs.skill_id not in smap]
    overlap = [s for s in required if s in smap]
    overlap_ids = set(overlap) | {rs.skill_id for rs in maharat_only}
    if required and len(overlap_ids) < max(1, len(required) // 2):
        return None  # حداقل نیمی از مهارت‌های الزامی

    # مرحله دوم — رتبه‌بندی ترکیبی
    skill_fit = (len(overlap_ids) / len(required)) if required else 0.5
    if maharat_only:
        reasons.append(f"پوشش با پروفایل تأییدشده مهارت‌یار۳۶۰: "
                       f"{', '.join(rs.skill.name for rs in maharat_only)}")
    reasons.append(f"تطبیق مهارت: {len(overlap_ids)} از {len(required)} مهارت الزامی "
                   f"({', '.join(smap[s]['skill_name'] for s in overlap) or '—'})")
    for s in required:
        if s not in smap:
            missing.append(smap.get(s, {}).get("skill_name") or
                           next((rs.skill.name for rs in problem.required_skills
                                 if rs.skill_id == s), str(s)))

    verified = [smap[s] for s in overlap if smap[s]["source"] in ("verified", "imported")]
    evidence = sum(smap[s]["level"] for s in overlap) / (5 * max(1, len(overlap)))
    if verified:
        reasons.append(f"شواهد اعتبارسنجی‌شده: {len(verified)} مهارت با سطح ≥{min(v['level'] for v in verified)}")
    if boost:
        # ترکیب شواهد محلی و مهارت‌یار (سطح ۰..۱۰۰ مهارت‌یار → ۰..۱)
        evidence = 0.7 * evidence + 0.3 * boost["avg_level"]
        reasons.extend(boost["reasons"][:3])

    profile_fit = 0.0
    if user.user_type == "professor":
        profile_fit += 0.7
        reasons.append("مسئولیت علمی: استاد واجد شرایط هدایت علمی مسئله")
    else:
        profile_fit += 0.45
        if user.degree:
            profile_fit += 0.2
            reasons.append(f"مقطع تحصیلی مرتبط: {user.degree}")
    if user.department and problem.category and user.department[:6] in problem.category:
        profile_fit += 0.3
        reasons.append(f"تناسب موضوعی گروه: {user.department}")

    conditions_fit = 0.5
    if problem.work_mode == WorkMode.remote:
        conditions_fit = 0.8
        reasons.append("امکان اجرا با دورکاری کامل")
    elif problem.location and user.department and problem.location[:4] in user.department:
        conditions_fit = 0.9

    score = (WEIGHTS["skill_fit"] * skill_fit + WEIGHTS["evidence"] * evidence +
             WEIGHTS["profile_fit"] * profile_fit + WEIGHTS["conditions_fit"] * conditions_fit)
    return {"score": round(min(score, 1.0), 4), "reasons": reasons, "missing": missing}


def run_matching(db: Session, problem: IndustrialProblem, run_by: str) -> MatchRun:
    run = MatchRun(problem_id=problem.id, algorithm_version=ALGORITHM_VERSION,
                   status=MatchRunStatus.completed, weights=WEIGHTS, created_by=run_by,
                   finished_at=utcnow())
    db.add(run)
    db.flush()
    results = []
    for u in db.query(User).filter(User.is_active.is_(True),
                                   User.user_type.in_(["student", "professor"])).all():
        out = score_candidate(db, problem, u)
        if out:
            out["user"] = u
            results.append(out)
    results.sort(key=lambda r: r["score"], reverse=True)
    for i, r in enumerate(results[:50], start=1):
        db.add(MatchResult(match_run_id=run.id, user_id=r["user"].id, rank=i,
                           score=r["score"], reasons=r["reasons"], missing=r["missing"],
                           data_quality_note="بر مبنای آخرین snapshots مهارتی کاربر؛ امتیاز=رتبه‌بندی کمکی، نه احتمال موفقیت"))
    run.stats = {"candidates_evaluated": len(results), "candidates_returned": min(len(results), 50),
                 "hard_filtered": len(results)}
    return run


def recommend_problems_for_user(db: Session, user: User, limit: int = 10) -> list[dict]:
    """مسئولیت معکوس: پیشنهاد مسئله به دانشجو/استاد با دلیل."""
    from ..models import ProblemStatus
    from ..serializers import problem_brief
    published = db.query(IndustrialProblem).filter(
        IndustrialProblem.status == ProblemStatus.published).all()
    smap = _skill_map(db, user.id)
    scored = []
    for p in published:
        reqs = p.required_skills
        if not reqs:
            continue
        boost = _maharat_boost(db, p, user.id)
        covered = set((boost or {}).get("covered_skills", {}))
        overlap = [rs for rs in reqs if rs.skill_id in smap or rs.skill.name in covered]
        if not overlap:
            continue
        skill_fit = len(overlap) / len(reqs)
        reasons = [f"مهارت «{rs.skill.name}» در پروفایل شما ثبت شده است" for rs in overlap[:3]]
        if boost:
            reasons = boost["reasons"][:2] + reasons[:2]
        missing = [rs.skill.name for rs in reqs if rs.skill_id not in smap and rs.skill.name not in covered]
        score = 0.6 * skill_fit + (0.2 if user.user_type == "professor" else 0.1) + 0.2 * (
            sum(min(smap[rs.skill_id]["level"], 5) for rs in overlap if rs.skill_id in smap)
            / (5 * len(overlap))) + 0.1 * (boost or {}).get("avg_level", 0.0)
        scored.append({"problem": problem_brief(p), "score": round(min(score, 1.0), 4),
                       "reasons": reasons, "missing": missing})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]
