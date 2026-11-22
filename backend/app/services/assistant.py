"""دستیار تبدیل «نیاز مبهم صنعت» به «مسئلهٔ اجرایی» — قاعدمحور و نسخه‌دار (v1.1.0).

اصل طراحی: خروجی دستیار «پیش‌نویس + برآورد» است، نه وعدهٔ قطعی هوش مصنوعی؛
برآورد بودجه/زمان با پرچم is_estimate=True برگردانده می‌شود و مسئله تنها پس از
تأیید کارشناس/نماینده صنعتی ساخته می‌شود (تصمیم نهایی انسانی).

حریم خصوصی: پردازش کاملاً داخل سامانه و قاعدمحور است — هیچ متن محرمانه به
سرویس بیرونی ارسال نمی‌شود (قاعدهٔ امنیت هوش مصنوعی فاز اعتماد).
"""
import re

ALGORITHM_VERSION = "intake-v1.0"

# واژه‌نامهٔ دامنه: کلیدواژه‌های فارسی/انگلیسی → مهارت موردنیاز
_SKILL_HINTS: list[tuple[tuple[str, ...], str]] = [
    (("هوش مصنوعی", "یادگیری ماشین", "machine learning", "ai", "مدل", "پیش‌بینی"), "یادگیری ماشین"),
    (("بینایی", "تصویر", "دوربین", "vision", "تشخیص عیب"), "بینایی ماشین"),
    (("داده", "تحلیل داده", "داشبورد", "گزارش‌سازی", "data"), "تحلیل داده"),
    (("پایش", "سنسور", "iot", "اینترنت اشیا", "iioT"), "اینترنت اشیای صنعتی"),
    (("کنترل", "اتوماسیون", "plc", "خط تولید"), "کنترل و اتوماسیون صنعتی"),
    (("وب", "سایت", "اپلیکیشن", "نرم‌افزار", "اپ", "software"), "توسعه نرم‌افزار"),
    (("شبکه", "زیرساخت", "امنیت", "security"), "امنیت شبکه"),
    (("بهره‌وری انرژی", "انرژی", "مصرف سوخت"), "بهینه‌سازی انرژی"),
    (("زنجیره تأمین", "لجستیک", "انبارداری", " موجودی"), "بهینه‌سازی زنجیره تأمین"),
    (("فرایند", "بهبود", "لین", "lean", "کاهش ضایعات"), "مهندسی صنایع و بهبود فرایند"),
    (("مواد", "آلیاژ", "خوردگی", "پوشش"), "مهندسی مواد"),
    (("مکانیک", "تعمیرات", "نگهداری", "تعمییر", "pm"), "نگهداری و تعمییرات"),
    (("آموزش", "دوره", "شبیه‌ساز آموزشی"), "طراحی آموزش و شبیه‌سازی"),
]

_QUESTIONS = [
    {"key": "need_text", "q": "نیاز یا ایدهٔ خود را با چند جملهٔ عادی بنویسید (همان‌طور که هست)"},
    {"key": "current_state", "q": "وضعیت موجود در سازمان چگونه است؟ چه چیزی اکنون رخ می‌دهد؟"},
    {"key": "real_pain", "q": "مشکل واقعی و قابل‌لمس کدام است؟ هزینه یا ضرر فعلی چیست؟"},
    {"key": "data_assets", "q": "چه داده، تجهیزات یا دسترسی‌هایی موجود است؟ (فرمت، حجم، مالکیت)"},
    {"key": "measurable_outcome", "q": "نتیجهٔ مطلوب را چگونه اندازه می‌گیرید؟ (عدد یا وضعیت روشن)"},
    {"key": "success_criteria", "q": "اگر پروژه موفق باشد، چه چیزی تحویل می‌گیرید؟"},
    {"key": "constraints", "q": "محدودیت بودجه، زمان و محرمانگی چیست؟"},
]


def questionnaire() -> list[dict]:
    """پرسش‌های راهنمای ساخت مسئله — برای ویزارد فرانت."""
    return [{"key": q["key"], "question": q["q"], "optional": q["key"] == "constraints"}
            for q in _QUESTIONS]


def _guess_skills(text: str) -> list[str]:
    t = text.lower()
    found = []
    for keys, skill in _SKILL_HINTS:
        if any(k in t for k in keys):
            if skill not in found:
                found.append(skill)
    return found[:6]


def _title_from(answers: dict) -> str:
    pain = (answers.get("real_pain") or "").strip()
    need = (answers.get("need_text") or "").strip()
    src = pain or need or "مسئلهٔ صنعتی بدون عنوان"
    first = re.split(r"[.!؟?\n؛;]", src)[0].strip()
    if len(first) > 90:
        first = first[:87] + "…"
    return first or "مسئلهٔ صنعتی بدون عنوان"


def _estimate(answers: dict, skills: list[str]) -> dict:
    """برآورد صرفاً راهنما — همیشه نیازمند تأیید کارشناس است."""
    n = len(answers.get("measurable_outcome") or "") + len(answers.get("success_criteria") or "")
    base_weeks = 6 if len(skills) <= 2 else (10 if len(skills) <= 4 else 14)
    if n > 120:
        base_weeks = max(4, base_weeks - 2)
    budget_low, budget_high = 60, 120
    if len(skills) >= 3:
        budget_low, budget_high = 120, 250
    if "یادگیری ماشین" in skills or "بینایی ماشین" in skills:
        budget_low, budget_high = budget_low * 1.3, budget_high * 1.3
    return {
        "duration_weeks": base_weeks,
        "budget_range_million_IRR": [int(budget_low), int(budget_high)],
        "is_estimate": True,
        "disclaimer": "برآورد صرفاً راهنماست و پیش از هر تعهدی باید توسط کارشناس دفتر ارتباط با صنعت تأیید شود",
    }


def build_draft(answers: dict) -> dict:
    """پاسخ‌های راهنما → پیش‌نویس استاندارد مسئله (دامنه، تحویل‌دادنی، معیار پذیرش، مهارت، خلأها)."""
    a = {k: (answers.get(k) or "").strip() for k in
         ["need_text", "current_state", "real_pain", "data_assets",
          "measurable_outcome", "success_criteria", "constraints"]}
    text_all = " ".join(a.values())
    skills = _guess_skills(text_all)
    if not skills:
        skills = ["تحلیل داده"]  # پیش‌فرض محافظه‌کارانه تا کارشناس اصلاح کند

    missing = []
    if not a["measurable_outcome"]:
        missing.append("معیار کمی پذیرش — «نتیجهٔ مطلوب چگونه اندازه می‌شود؟» پاسخ داده نشده است")
    if not a["data_assets"]:
        missing.append("وضعیت داده و دسترسی‌ها نامشخص است")
    if not a["success_criteria"]:
        missing.append("تحویل‌دادنی نهایی (خروجی قابل‌آزمایش) تعیین نشده است")
    if not a["constraints"]:
        missing.append("محدودیت بودجه، زمان و محرمانگی اعلام نشده است")
    if not a["current_state"]:
        missing.append("وضعیت موجود فرایند مستند نشده است")

    deliverable = a["success_criteria"] or \
        "خروجی قابل‌آزمایش متناسب با مشکل اصلی (پس از تأیید کارشناس دقیق‌تر می‌شود)"
    acceptance = []
    if a["measurable_outcome"]:
        acceptance.append(f"سنجش نتیجه: {a['measurable_outcome']}")
    if a["data_assets"]:
        acceptance.append("دسترسی به داده/تجهیزات اعلام‌شده پیش از شروع تحویل داده می‌شود")
    acceptance.append("دموی پایانی با حضور نمایندهٔ صنعتی و پذیرش مکتوب")

    filled = sum(1 for v in a.values() if v) / len(a)
    confidence = int(filled * 100)

    draft = {
        "title": _title_from(a),
        "summary": (a["real_pain"] or a["need_text"] or "")[:400],
        "scope": {
            "current_state": a["current_state"],
            "problem_statement": a["real_pain"] or a["need_text"],
            "in_scope_hint": "محدودهٔ پیشنهادی بر مبنای پاسخ‌ها — پیش از انتشار نیازمند تأیید کارشناس",
        },
        "deliverable": deliverable,
        "acceptance_criteria": acceptance,
        "required_skills": skills,
        "missing_info": missing,
        "estimate": _estimate(a, skills),
        "data_confidence": confidence,
        "generated_by": ALGORITHM_VERSION,
        "human_review_required": True,
    }
    return draft
