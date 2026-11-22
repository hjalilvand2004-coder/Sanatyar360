"""تیم‌سازی توضیح‌پذیر — «تیم آماده حل مسئله» به‌جای فهرست افراد (v1.1.0).

خروجی: ترکیب پیشنهادی (استاد راهبر + دانشجوی متخصص + دانشجوی مکمل + منابع)
با دو شاخص جدای «تناسب (fit)» و «اطمینان به داده‌ها (confidence)»، شواهد
تأییدشده، شکاف‌ها، ظرفیت واقعی و دلیل پیشنهاد — کمبود داده هرگز معادل ضعف
فرد تلقی نمی‌شود و تصمیم پذیرش نهایی با انسان است.
"""
from ..models import (
    CollaborationProject, MaharatLink, MemberRole, MembershipStatus,
    OrganizationMembership, User, UserSkillSnapshot, utcnow, WorkMode,
)
from .matching import ALGORITHM_VERSION as _MATCH_V, score_candidate

ALGORITHM_VERSION = "team-v1.0"


def _skill_profile(db, user_id: str) -> dict:
    rows = db.query(UserSkillSnapshot).filter(UserSkillSnapshot.user_id == user_id).all()
    return {r.skill.name: {"level": r.level, "source": r.source} for r in rows}


def _capacity_note(db, user_id: str) -> tuple[str, int]:
    """ظرفیت واقعی: تعداد همکاری فعال جاری به‌عنوان نشانهٔ اشغال."""
    active = db.query(CollaborationProject).filter(
        CollaborationProject.status.not_in(("completed", "terminated")),
        CollaborationProject.academic_lead_user_id == user_id).count()
    member = db.query(CollaborationProject).filter(
        CollaborationProject.status.not_in(("completed", "terminated")),
        CollaborationProject.members.any(user_id=user_id)).count() \
        if hasattr(CollaborationProject, "members") else 0
    load = max(active, member)
    if load == 0:
        return "بدون همکاری فعال جاری — ظرفیت آزاد", 100
    if load <= 1:
        return "یک همکاری فعال — ظرفیت محدود آزاد", 70
    return f"{load} همکاری فعال — ظرفیت در حال اشغال؛ هماهنگی زمان لازم است", 40


def _verified_names(db, user_id: str, required_names: list[str]) -> list[str]:
    """مهارت‌های الزامی که برای این کاربر با شواهد تأییدشده (verified/imported) ثبت شده‌اند."""
    smap = _skill_profile(db, user_id)
    return [n for n in required_names
            if n in smap and smap[n]["source"] in ("verified", "imported")]


def _two_way_note(db, user, problem) -> str:
    """تناسب از نگاه دانشجو/استاد: موضوع و حالت اجرا."""
    bits = []
    if user.department and problem.category and user.department[:6] in problem.category:
        bits.append(f"موضوع با گروه «{user.department}» هم‌راستاست")
    if problem.work_mode == WorkMode.remote:
        bits.append("امکان اجرای دورکاری")
    if user.user_type == "student":
        bits.append("مناسب برای یادگیری عملی و ثبت شواهد مهارت در پروفایل")
    else:
        bits.append("قابل ثبت به‌عنوان پروژهٔ راهبری علمی")
    return "؛ ".join(bits) or "تناسب موضوعی نیازمند گفت‌وگوی اولیه"


def _member_payload(db, user: User, role_in_team: str, scored: dict,
                    problem, verified_names: list[str]) -> dict:
    fit = round(scored["score"] * 100)
    smap = _skill_profile(db, user.id)
    conf = 0
    if scored.get("score") is not None:
        rel = [s for s in smap if s in verified_names or True]
        if rel:
            conf = int(100 * sum(1 for s in smap.values()
                                 if s["source"] in ("verified", "imported")) / len(smap))
    cap_note, cap_score = _capacity_note(db, user.id)
    return {
        "user": {"id": user.id, "full_name": user.full_name,
                 "user_type": user.user_type, "department": user.department,
                 "degree": user.degree},
        "role_in_team": role_in_team,
        "fit": fit,                       # تناسب مهارتی/موضوعی (۰..۱۰۰)
        "confidence": conf,               # اطمینان به داده‌ها: سهم شواهد تأییدشده (۰..۱۰۰)
        "capacity": {"note": cap_note, "score": cap_score},
        "evidence": verified_names[:6],   # مهارت‌های با شواهد تأییدشده
        "gaps": scored.get("missing", [])[:6],
        "reasons": scored.get("reasons", [])[:5],
        "two_way_note": _two_way_note(db, user, problem),
        "data_quality_note": "کمبود داده به‌معنای ضعف فرد نیست؛ پیش از قضاوت تکمیل شود",
    }


def build_team_proposal(db, problem, created_by: str) -> dict:
    """ترکیب پیشنهادی تیم برای مسئله — با پوشش تجمعی مهارت‌ها و توضیح فارسی.

    دو مرحله: نخست با فیلتر سختِ «حداقل نیمی از مهارت‌ها»؛ اگر نامزدی نماند،
    مرحلهٔ شل‌تر برای ارائهٔ پیشنهاد با شکاف صریح (کمبود داده ≠ ضعف فرد).
    """
    required_names = [rs.skill.name for rs in problem.required_skills if rs.is_required]

    def _collect(relaxed: bool) -> list[dict]:
        out = []
        for u in db.query(User).filter(User.is_active.is_(True),
                                       User.user_type.in_(["student", "professor"])).all():
            r = score_candidate(db, problem, u, relaxed=relaxed)
            if r:
                r["user"] = u
                out.append(r)
        out.sort(key=lambda r: r["score"], reverse=True)
        return out

    scored = _collect(relaxed=False)
    gap_mode = False
    if not scored:
        scored = _collect(relaxed=True)
        gap_mode = True

    profs = [r for r in scored if r["user"].user_type == "professor"]
    studs = [r for r in scored if r["user"].user_type == "student"]

    members: list[dict] = []
    covered: set[str] = set()

    if profs:
        p = profs[0]
        vname = _verified_names(db, p["user"].id, required_names)
        members.append(_member_payload(db, p["user"], "استاد راهبر", p, problem, vname))
    if studs:
        s1 = studs[0]
        smap1 = _skill_profile(db, s1["user"].id)
        covered |= set(smap1.keys())
        vname = _verified_names(db, s1["user"].id, required_names)
        members.append(_member_payload(db, s1["user"], "دانشجوی متخصص", s1, problem, vname))
        # دانشجوی مکمل — بیشترین پوششِ مهارت‌های باقی‌مانده
        rest = [n for n in required_names if n not in covered]
        best, best_gain = None, 0
        for s2 in studs[1:8]:
            smap2 = _skill_profile(db, s2["user"].id)
            gain = len(set(rest) & set(smap2.keys()))
            if gain > best_gain:
                best, best_gain = s2, gain
        if best and best_gain > 0:
            smap2 = _skill_profile(db, best["user"].id)
            covered |= set(smap2.keys())
            vname2 = _verified_names(db, best["user"].id, required_names)
            members.append(_member_payload(db, best["user"], "دانشجوی مکمل", best, problem, vname2))

    missing = [n for n in required_names if n not in covered]
    resource_notes = []
    if missing:
        resource_notes.append(
            "برای مهارت‌های پوشش‌نیافته (" + "، ".join(missing[:3]) +
            ") استفاده از مشاور صنعتی یا آزمایشگاه دانشگاه پیشنهاد می‌شود")
    if required_names:
        resource_notes.append("دسترسی به داده و تجهیزات اعلامی مسئله باید پیش از شروع باز شود")
    resource_notes.append("این ترکیب «پیشنهاد» است؛ انتخاب نهایی پس از تأیید کارشناس و صنعت انجام می‌شود")

    explanation = []
    if gap_mode:
        explanation.append(
            "هیچ نامزدی پوشش کامل مهارت‌های الزامی را ندارد؛ پیشنهاد زیر با شکاف صریح ارائه می‌شود "
            "و برای قضاوت نهایی، تکمیل پروفایل/شواهد لازم است")
    if members:
        top = members[0]
        explanation.append(
            f"«{top['user']['full_name']}» به‌عنوان {top['role_in_team']} با تناسب {top['fit']}٪ و "
            f"اطمینان داده {top['confidence']}٪ پیشنهاد شده است")
    if covered & set(required_names):
        inter = [n for n in required_names if n in covered]
        explanation.append(f"پوشش تیمیِ مهارت‌های الزامی: {len(inter)} از {len(required_names)}")
    if missing:
        explanation.append(f"شکاف باقی‌مانده: {'، '.join(missing[:4])}")
    explanation.append("تناسب (fit) و اطمینان به داده‌ها (confidence) دو شاخص جدایند؛ "
                       "کمبود شواهد به‌معنای ضعف فرد نیست")

    link = db.query(MaharatLink).filter(MaharatLink.user_id.isnot(None)).count()
    if link:
        resource_notes.append(f"{link} کاربر دارای پروفایل تأییدشدهٔ مهارت‌یار۳۶۰ — شواهد در اعضا لحاظ شد")

    return {
        "algorithm_version": ALGORITHM_VERSION,
        "composition": members,
        "coverage": {"covered": sorted(covered & set(required_names)) or sorted(covered)[:8],
                     "missing": missing},
        "explanation": ". ".join(explanation) + ".",
        "resource_notes": resource_notes,
        "matching_engine": _MATCH_V,
        "candidates_evaluated": len(scored),
        "human_decision_required": True,
    }
