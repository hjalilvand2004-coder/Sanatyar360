"""تحلیل‌ها: خلاصه شاخص‌ها، تقاضای مهارت، شبکه همکاری، کیفیت داده."""
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..core.deps import get_current_user, get_memberships
from ..db import get_db
from ..models import (
    Application, CollaborationProject, CommercializationCase, IndustrialProblem,
    MarketDataSource, MarketObservation, MemberRole, Organization,
    ProblemRequiredSkill, ProblemStatus, ProjectStatus, Skill, User,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

ANALYST_ROLES = {MemberRole.cio_manager, MemberRole.cio_expert, MemberRole.university_admin,
                 MemberRole.policy_maker, MemberRole.sys_admin, MemberRole.comm_expert}


def _require_analyst(memberships):
    if not ({m.role for m in memberships} & ANALYST_ROLES):
        raise HTTPException(status_code=403, detail={
            "code": "forbidden",
            "message": "تحلیل‌ها فقط برای مدیر دانشگاه/دفتر/سیاست‌گذار مجاز است"})


@router.get("/summary")
def summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_analyst(get_memberships(db, user))
    problems_total = db.query(IndustrialProblem).count()
    published = db.query(IndustrialProblem).filter(
        IndustrialProblem.status == ProblemStatus.published).count()
    converted = db.query(IndustrialProblem).filter(
        IndustrialProblem.status == ProblemStatus.converted_to_project).count()
    apps_total = db.query(Application).count()
    apps_accepted = db.query(Application).filter_by(status="accepted").count()
    projects_total = db.query(CollaborationProject).count()
    completed = db.query(CollaborationProject).filter(
        CollaborationProject.status == ProjectStatus.completed).count()
    active = db.query(CollaborationProject).filter(
        CollaborationProject.status == ProjectStatus.active).count()

    # زمان تبدیل مسئله به همکاری (میانگین اختلاف created_at مسئله و پروژه)
    conv_days = []
    for p in db.query(CollaborationProject).filter(CollaborationProject.problem_id.isnot(None)).all():
        prob = db.get(IndustrialProblem, p.problem_id)
        if prob:
            conv_days.append((p.created_at - prob.created_at).total_seconds() / 86400)
    avg_conv_days = round(sum(conv_days) / len(conv_days), 1) if conv_days else None

    # نرخ همکاری مجدد صنعت
    by_org = defaultdict(int)
    for p in db.query(CollaborationProject).all():
        by_org[p.industry_org_id] += 1
    repeat = sum(1 for v in by_org.values() if v > 1)

    return {
        "problems": {"total": problems_total, "published": published,
                     "converted_to_project": converted,
                     "conversion_rate": round(converted / problems_total, 3) if problems_total else None},
        "applications": {"total": apps_total, "accepted": apps_accepted,
                         "acceptance_rate": round(apps_accepted / apps_total, 3) if apps_total else None},
        "collaborations": {"total": projects_total, "active": active, "completed": completed,
                           "completion_rate": round(completed / projects_total, 3) if projects_total else None,
                           "repeat_industry_partners": repeat},
        "avg_days_problem_to_collaboration": avg_conv_days,
        "commercialization_cases": db.query(CommercializationCase).count(),
        "note": "شاخص‌های اولیه بر مبنای داده همین سامانه است؛ با بزرگ‌شدن داده معنا پیدا می‌کند",
    }


@router.get("/skill-demand")
def skill_demand(months: int = 6, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    _require_analyst(get_memberships(db, user))
    # تقاضای ثبت‌شده در مسائل سامانه
    problem_counts = (db.query(Skill.name, func.count(ProblemRequiredSkill.id))
                      .join(ProblemRequiredSkill, ProblemRequiredSkill.skill_id == Skill.id)
                      .group_by(Skill.name).all())
    # تقاضای بازار از منابع مجاز (آگهی/نظرسنجی)
    months_list = [(datetime.now(timezone.utc) - timedelta(days=30 * i)).strftime("%Y-%m")
                   for i in range(months - 1, -1, -1)]
    obs = (db.query(MarketObservation.skill_id, Skill.name,
                    MarketObservation.observed_month, MarketObservation.demand_count,
                    MarketDataSource.name.label("source"), MarketDataSource.coverage_note)
           .join(Skill, Skill.id == MarketObservation.skill_id)
           .join(MarketDataSource, MarketDataSource.id == MarketObservation.source_id)
           .filter(MarketObservation.observed_month.in_(months_list)).all())
    by_month = defaultdict(int)
    by_skill_total = defaultdict(int)
    sources = set()
    for o in obs:
        by_month[o.observed_month] += o.demand_count
        by_skill_total[o.name] += o.demand_count
        sources.add(o.source)
    top_skills = sorted(by_skill_total.items(), key=lambda x: -x[1])[:15]
    # مهارت‌های نوظهور: مقایسه دو نیم‌بازه
    half = max(1, len(months_list) // 2)
    first, second = defaultdict(int), defaultdict(int)
    for o in obs:
        idx = months_list.index(o.observed_month)
        (first if idx < half else second)[o.name] += o.demand_count
    emerging = [{"skill": s, "growth": round(second.get(s, 0) / max(1, first.get(s, 0)), 2)}
                for s in set(first) | set(second)
                if second.get(s, 0) > first.get(s, 0)]
    emerging.sort(key=lambda x: -x["growth"])
    return {
        "market_by_month": [{"month": m, "demand": by_month.get(m, 0)} for m in months_list],
        "market_top_skills": [{"skill": s, "demand": d} for s, d in top_skills],
        "problems_demand": [{"skill": s, "count": c} for s, c in
                            sorted(problem_counts, key=lambda x: -x[1])],
        "emerging_skills": emerging[:10],
        "sources": sorted(sources),
        "coverage_note": "تغییر تعداد آگهی لزوماً تغییر کل تقاضا نیست؛ پوشش منابع و تکراری‌ها لحاظ شود",
        "min_sample_threshold": 5,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/collaboration-network")
def collaboration_network(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_analyst(get_memberships(db, user))
    projects = db.query(CollaborationProject).all()
    nodes, edges = {}, defaultdict(list)
    orgs_cache = {}

    def org_node(org_id):
        if org_id not in orgs_cache:
            orgs_cache[org_id] = db.get(Organization, org_id)
        o = orgs_cache[org_id]
        if not o:
            return None
        nid = f"org:{o.id}"
        if nid not in nodes:
            nodes[nid] = {"id": nid, "label": o.name, "kind": o.org_type.value, "projects": 0}
        return nid

    for p in projects:
        io, uo = org_node(p.industry_org_id), org_node(p.university_org_id)
        if not io or not uo:
            continue
        nodes[io]["projects"] += 1
        nodes[uo]["projects"] += 1
        key = (io, uo)
        edge = next((e for e in edges[key] if p.id not in e["project_ids"]), None)
        for e in edges[key]:
            e["weight"] += 1
            e["project_ids"].append(p.id)
            e["project_codes"].append(p.code)
        if not any(p.id in e["project_ids"] for e in edges[key]):
            edges[key].append({"from": io, "to": uo, "weight": 1,
                               "project_ids": [p.id], "project_codes": [p.code]})
    lead_cache = {}
    for p in projects:
        lead = lead_cache.setdefault(p.academic_lead_user_id, db.get(User, p.academic_lead_user_id))
        if lead:
            nid = f"user:{lead.id}"
            if nid not in nodes:
                nodes[nid] = {"id": nid, "label": lead.full_name, "kind": "academic_lead",
                              "projects": 0}
            nodes[nid]["projects"] += 1
            uo = org_node(p.university_org_id)
            if uo and not any(e["from"] == uo and e["to"] == nid for e in
                              [x for es in edges.values() for x in es]):
                edges[(uo, nid)].append({"from": uo, "to": nid, "weight": 1,
                                         "project_ids": [p.id], "project_codes": [p.code]})
    all_edges = [e for es in edges.values() for e in es]
    return {
        "nodes": list(nodes.values()),
        "edges": all_edges,
        "stats": {
            "active_partners": len([n for n in nodes.values() if n["kind"] == "industry"]),
            "universities": len([n for n in nodes.values() if n["kind"] == "university"]),
            "total_projects": len(projects),
            "repeated_collaborations": len([e for e in all_edges if e["weight"] > 1]),
        },
        "note": "هر یال به همکاری واقعی قابل ردیابی است (AC-11)؛ مرکزیت معیار کیفیت فردی نیست",
    }


@router.get("/quality")
def data_quality(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    _require_analyst(get_memberships(db, user))
    total_p = db.query(IndustrialProblem).count()
    with_criteria = sum(1 for p in db.query(IndustrialProblem).all() if p.acceptance_criteria)
    dup_skills = (db.query(ProblemRequiredSkill.problem_id, Skill.name,
                           func.count(ProblemRequiredSkill.id).label("c"))
                  .join(Skill, Skill.id == ProblemRequiredSkill.skill_id)
                  .group_by(ProblemRequiredSkill.problem_id, Skill.name)
                  .having(func.count(ProblemRequiredSkill.id) > 1).count())
    obs_total = db.query(MarketObservation).count()
    latest_source = db.query(func.max(MarketDataSource.last_fetched_at)).scalar()
    return {
        "problems_with_acceptance_criteria_pct": round(with_criteria / total_p, 3) if total_p else None,
        "duplicate_skill_rows": dup_skills,
        "market_observations_total": obs_total,
        "market_data_freshness": latest_source.isoformat() if latest_source else None,
        "note": "شاخص‌های کیفیت داده برای نمایش در داشبورد مدیر",
    }
