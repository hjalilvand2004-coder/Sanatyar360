"""کلاینت یکپارچگی با زیرسیستم مهارتیار۳۶۰ — اکوسیستم دانشجویار۳۶۰.

ارتباط تنگاتنگ صنعت‌یار ↔ مهارت‌یار:
  1) واژه‌نامه مهارت (کد، نام فارسی/انگلیسی، مترادف‌ها، دسته) → نرمال‌سازی مهارت‌های
     مسئله‌های صنعتی و تطبیق معنایی با پروفایل دانشجو.
  2) پروفایل مهارتی تأییدشده دانشجو (سطح ۰ تا ۱۰۰ به‌ازای هر مهارت + شواهد) →
     نمایش در صنعت‌یار و تقویت موتور تطبیق با شواهد معتبر.
  3) شکاف مهارتی دانشجو نسبت به مهارت‌های الزامی هر مسئله (پنل راهنمای دانشجو).
  4) تطبیق شغلی و آمار اکوسیستم برای تحلیل‌ها.

طراحی مقاوم: در نبود دسترسی به مهارتیار، همه توابع None/empty برمی‌گردانند و
سامانه با «حالت آفلاین» به کار عادی ادامه می‌دهد (تخریب تدریجی، نه شکست).
اعتبارنامه مهارتیار هرگز ذخیره نمی‌شود؛ فقط سطوح مهارتی و خلاصه شواهد.
"""
import base64
import json
import time
import urllib.request
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..core.config import settings
from ..models import IntegrationRun, MaharatLink, utcnow

# ---------- نرمال‌سازی متن فارسی/انگلیسی برای تطبیق مهارت‌ها ----------

_CHAR_MAP = {"ك": "ک", "ي": "ی", "ی": "ی", "أ": "ا", "إ": "ا", "آ": "ا", "ة": "ه", "ؤ": "و"}


def norm(s: str | None) -> str:
    if not s:
        return ""
    s = s.lower().replace("\u200c", " ").replace("\u200f", "").replace("\u200e", "")
    s = "".join(_CHAR_MAP.get(ch, ch) for ch in s)
    return " ".join(s.split())


def _skill_index(skills: list[dict]) -> dict[str, dict]:
    """نمایه جست‌وجوی مهارت بر اساس نام فارسی/انگلیسی، کد و مترادف‌ها."""
    idx: dict[str, dict] = {}
    for sk in skills:
        keys = {norm(sk.get("name_fa")), norm(sk.get("name_en")), norm(sk.get("code"))}
        keys.update(norm(a) for a in (sk.get("aliases") or []))
        for k in list(keys):
            if k:
                keys.add(k.replace(" ", ""))
                idx[k] = sk
    return idx


class MaharatUnavailable(Exception):
    pass


def _decode_exp(token: str) -> float:
    """انقضای توکن JWT مهارتیار — برای مدیریت کش."""
    try:
        p = token.split(".")[1]
        p += "=" * (-len(p) % 4)
        return float(json.loads(base64.urlsafe_b64decode(p)).get("exp", 0))
    except Exception:
        return 0.0


class MaharatClient:
    """کلاینت HTTP استاندارد-کتابخانه‌ای (بدون وابستگی جدید — سازگار با پرتیبل)."""

    def __init__(self, api_url: str | None = None, service_email: str | None = None,
                 service_password: str | None = None, timeout: int | None = None):
        self.api_url = (api_url or settings.maharat_api_url).rstrip("/")
        self.service_email = service_email or settings.maharat_service_email
        self.service_password = service_password or settings.maharat_service_password
        self.timeout = timeout or settings.maharat_timeout
        self._token: str | None = None
        self._token_exp = 0.0

    # --- HTTP ---
    def _request(self, method: str, path: str, body: dict | None = None,
                 token: str | None = None) -> dict:
        url = f"{self.api_url}/{path.lstrip('/')}"
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/json")
        if data:
            req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:  # شبکه، تایم‌اوت، 4xx/5xx
            raise MaharatUnavailable(f"{type(e).__name__}: {e}") from e

    def _service_token(self, force: bool = False) -> str:
        if not force and self._token and time.time() < self._token_exp - 60:
            return self._token
        d = self._request("POST", "auth/login", {
            "email": self.service_email, "password": self.service_password})
        self._token = d.get("access_token") or ""
        self._token_exp = _decode_exp(self._token)
        if not self._token:
            raise MaharatUnavailable("login failed: no access_token")
        return self._token

    # --- APIهای مهارتیار ---
    def health(self) -> dict:
        return self._request("GET", "health")

    def skills(self) -> list[dict]:
        return self._request("GET", "skills", token=self._service_token()).get("items", [])

    def careers(self) -> list[dict]:
        return self._request("GET", "careers", token=self._service_token()).get("items", [])

    def users(self) -> list[dict]:
        return self._request("GET", "users", token=self._service_token()).get("items", [])

    def profile(self, profile_id: int, token: str | None = None) -> dict:
        tok = token or self._service_token()
        return self._request("GET", f"profiles/{profile_id}", token=tok)

    def career_matches(self, profile_id: int, token: str | None = None) -> list[dict]:
        tok = token or self._service_token()
        return self._request("GET", f"profiles/{profile_id}/career-matches", token=tok).get("items", [])

    # --- نگاشت کاربر مهارتیار ← پروفایل (پروفایل مستقل از شناسه کاربر است) ---
    def profile_by_email(self, email: str) -> dict | None:
        """یافتن پروفایل دانشجو از طریق ایمیل در فهرست کاربران + تطبیق نام با پروفایل."""
        users = self.users()
        u = next((x for x in users if (x.get("email") or "").lower() == email.lower()), None)
        if not u or u.get("role") != "student":
            return None
        target = norm(u.get("full_name"))
        n_students = sum(1 for x in users if x.get("role") == "student")
        # شناسه پروفایل‌ها از ۱ شماره‌گذاری می‌شوند؛ با تطبیق نام پیدا می‌کنیم
        for pid in range(1, max(n_students, 1) + 6):
            try:
                prof = self.profile(pid)
            except MaharatUnavailable:
                break
            if norm(prof.get("full_name")) == target:
                prof["_maharat_user_id"] = u.get("id")
                return prof
        return None

    def me_with_profile(self, token: str) -> dict | None:
        """با توکن خودِ دانشجو: /auth/me + یافتن پروفایل با تطبیق نام."""
        me = self._request("GET", "auth/me", token=token)
        target = norm(me.get("full_name"))
        users = self._request("GET", "users", token=token).get("items", []) \
            if me.get("role") == "admin" else []
        n_students = sum(1 for x in users if x.get("role") == "student") or 8
        for pid in range(1, n_students + 6):
            try:
                prof = self.profile(pid, token=token)
            except MaharatUnavailable:
                break
            if norm(prof.get("full_name")) == target:
                prof["_maharat_user_id"] = me.get("id")
                return prof
        return None


# ---------- کش واژه‌نامه (فرآیند-محلی با TTL) ----------

_DICTIONARY: dict | None = None
_DICTIONARY_AT = 0.0
_DICT_TTL = 24 * 3600
_IDX: dict[str, dict] = {}


def dictionary(client: MaharatClient | None = None, force: bool = False) -> dict | None:
    """واژه‌نامه مهارت مهارتیار: {skills, careers, idx, fetched_at, mode}."""
    global _DICTIONARY, _DICTIONARY_AT, _IDX
    if not force and _DICTIONARY and time.time() - _DICTIONARY_AT < _DICT_TTL:
        return _DICTIONARY
    c = client or MaharatClient()
    try:
        skills = c.skills()
        try:
            careers = c.careers()
        except MaharatUnavailable:
            careers = []
        _IDX = _skill_index(skills)
        _DICTIONARY = {"skills": skills, "careers": careers, "idx": _IDX,
                       "fetched_at": datetime.now(timezone.utc).isoformat()}
        _DICTIONARY_AT = time.time()
        return _DICTIONARY
    except MaharatUnavailable:
        return None


def match_maharat_skill(skill_name: str) -> dict | None:
    """مهارت صنعت‌یار ← مهارت واژه‌نامه مهارتیار (نام/انگلیسی/کد/مترادف)."""
    if not _IDX:
        d = dictionary()
        if not d:
            return None
    return _IDX.get(norm(skill_name)) or _IDX.get(norm(skill_name).replace(" ", ""))


# ---------- ساخت snapshot و ذخیره پیوند ----------

def build_levels(profile: dict) -> list[dict]:
    """سطح هر مهارت + خلاصه شواهد از پروفایل مهارتیار."""
    out = []
    for lv in profile.get("levels", []):
        br = lv.get("breakdown") or []
        top = br[0].get("title") if br else None
        out.append({
            "skill_code": lv.get("skill_code"), "skill_name_fa": lv.get("skill_name_fa"),
            "category": lv.get("category"), "level": round(float(lv.get("level") or 0), 1),
            "evidence_count": len(br), "top_evidence": top,
        })
    return out


def save_link(db: Session, user_id: str, profile: dict, careers: list[dict],
              source: str, is_sample: bool = False) -> MaharatLink:
    link = db.query(MaharatLink).filter_by(user_id=user_id).first()
    if not link:
        link = MaharatLink(user_id=user_id)
        db.add(link)
    levels = build_levels(profile)
    link.maharat_user_id = profile.get("_maharat_user_id")
    link.maharat_profile_id = profile.get("id")
    link.maharat_full_name = profile.get("full_name")
    link.major = profile.get("major")
    link.degree_level = profile.get("degree_level")
    link.university_name = profile.get("university_name")
    link.engine_mode = profile.get("engine_mode")
    link.levels_json = levels
    link.careers_json = careers
    link.skills_total = len(levels)
    link.verified_evidences = sum(x["evidence_count"] for x in levels)
    link.source = source
    link.is_sample = is_sample
    link.refreshed_at = utcnow()
    db.flush()
    return link


def link_by_email(db: Session, user_id: str, email: str) -> MaharatLink | None:
    """پیوند با حساب سرویس صنعت‌یار روی مهارتیار (server-to-server)."""
    c = MaharatClient()
    prof = c.profile_by_email(email)
    if not prof:
        return None
    try:
        careers = c.career_matches(prof["id"])
    except MaharatUnavailable:
        careers = []
    link = save_link(db, user_id, prof, careers, source="service_admin")
    _log_integration(db, ok=True, records=len(link.levels_json or []))
    return link


def link_by_token(db: Session, user_id: str, token: str) -> MaharatLink:
    """پیوند با توکن خودِ دانشجو (بدون ذخیره توکن)."""
    c = MaharatClient()
    prof = c.me_with_profile(token)
    if not prof:
        raise MaharatUnavailable("پروفایل مهارتی با این توکن یافت نشد")
    try:
        careers = c.career_matches(prof["id"], token=token)
    except MaharatUnavailable:
        careers = []
    link = save_link(db, user_id, prof, careers, source="self_token")
    _log_integration(db, ok=True, records=len(link.levels_json or []))
    return link


def refresh_link(db: Session, link: MaharatLink) -> bool:
    """به‌روزرسانی snapshot موجود؛ در صورت قطعی، snapshot قبلی حفظ می‌شود."""
    try:
        c = MaharatClient()
        if link.source == "self_token":
            return False  # توکن نگهداری نمی‌شود؛ دانشجو باید دوباره پیوند بزند
        prof = c.profile_by_email(link.user.email)
        if not prof:
            return False
        try:
            careers = c.career_matches(prof["id"])
        except MaharatUnavailable:
            careers = link.careers_json or []
        save_link(db, link.user_id, prof, careers, source=link.source)
        return True
    except MaharatUnavailable:
        return False


def _log_integration(db: Session, ok: bool, records: int = 0, note: str | None = None):
    db.add(IntegrationRun(system_name="maharatyar360", direction="import",
                          status="ok" if ok else "failed", records=records, note=note))


# ---------- شکاف مهارتی نسبت به مسئله + تقویت موتور تطبیق ----------

def skill_gap_for_problem(db: Session, problem, link: MaharatLink) -> dict:
    """شکاف مهارتی دانشجو نسبت به مهارت‌های الزامی مسئله — بر مبنای سطوح تأییدشده مهارتیار."""
    d = dictionary()
    levels = {norm(x.get("skill_code")): x for x in (link.levels_json or [])}
    items, covered = [], 0
    for rs in problem.required_skills:
        ms = match_maharat_skill(rs.skill.name)
        lv = levels.get(norm(ms.get("code"))) if ms else None
        level100 = lv["level"] if lv else None
        need = int(getattr(rs, "min_level", 3) or 3) * 20  # مقیاس صنعت‌یار 1..5 → 20..100
        if level100 is not None:
            covered += 1
            ok = level100 >= need
            items.append({
                "skill": rs.skill.name,
                "maharat_skill": ms.get("name_fa") if ms else None,
                "maharat_level": level100, "required_level": need,
                "gap": max(0, round(need - level100, 1)),
                "evidence_count": lv["evidence_count"] if lv else 0,
                "top_evidence": lv["top_evidence"] if lv else None,
                "verdict": "تأییدشده" if ok else "نیازمند تقویت",
            })
        else:
            items.append({
                "skill": rs.skill.name, "maharat_skill": None, "maharat_level": None,
                "required_level": need, "gap": None, "evidence_count": 0,
                "top_evidence": None, "verdict": "در مهارت‌یار ثبت نشده",
            })
    total = len(items) or 1
    return {
        "problem_id": problem.id, "coverage": round(covered / total, 3),
        "items": items,
        "mode": "live" if d else "cache/offline",
        "note": "سطوح بر مبنای مدارک و شواهد تأییدشده مهارتیار۳۶۰ است (مقیاس ۰ تا ۱۰۰)",
    }


def matching_boost(problem, link: MaharatLink | None) -> dict:
    """عامل مهارتیار در موتور تطبیق: مهارت‌های پوشش‌داده + شواهد تأییدشده.

    خروجی: {"covered_skills": {نام_مهارت: سطح/۱۰۰}, "avg_level": 0..1, "reasons": [...]}
    فقط وقتی snapshot معتبر وجود دارد مقدار می‌گیرد — در غیر این صورت بی‌اثر است.
    """
    if not link or not link.levels_json:
        return {}
    reasons, covered = [], {}
    for rs in problem.required_skills:
        ms = match_maharat_skill(rs.skill.name)
        if not ms:
            continue
        lv = next((x for x in link.levels_json
                   if norm(x.get("skill_code")) == norm(ms.get("code"))), None)
        if lv and lv.get("level", 0) > 0:
            covered[rs.skill.name] = lv["level"]
            reasons.append(f"مهارت‌یار۳۶۰: «{lv.get('skill_name_fa') or rs.skill.name}» "
                           f"تأییدشده با سطح {lv['level']:.0f}/۱۰۰ "
                           f"({lv.get('evidence_count', 0)} مدرک)")
    if not covered:
        return {}
    avg = sum(min(v, 100) for v in covered.values()) / (100 * len(covered))
    return {"covered_skills": covered, "avg_level": round(avg, 3), "reasons": reasons}


def status() -> dict:
    """وضعیت ارتباط با مهارتیار برای پنل مدیریت/تحلیل."""
    if not settings.maharat_enabled:
        return {"enabled": False, "mode": "disabled",
                "note": "یکپارچگی مهارتیار غیرفعال است (MAHARAT_ENABLED=0)"}
    try:
        h = MaharatClient().health()
        d = dictionary()
        return {"enabled": True, "mode": "live", "api_url": settings.maharat_api_url,
                "app": h.get("app"), "version": h.get("version"),
                "engine_mode": h.get("engine_mode"), "database": h.get("database"),
                "skills_count": len((d or {}).get("skills", [])),
                "careers_count": len((d or {}).get("careers", [])),
                "note": "ارتباط زنده با مهارتیار۳۶۰ برقرار است"}
    except MaharatUnavailable as e:
        return {"enabled": True, "mode": "offline", "api_url": settings.maharat_api_url,
                "note": f"مهارتیار در دسترس نیست — سامانه به‌صورت آفلاین ادامه می‌دهد ({e})"}


# ---------- داده نمونه (پرتیبل آفلاین) — برچسب «نمونه» ----------

def sample_snapshot() -> tuple[dict, list[dict]]:
    """snapshot نمونه هم‌شکل داده واقعی مهارتیار — فقط وقتی دسترسی نیست."""
    profile = {
        "id": 0, "full_name": "پروفایل نمونه اکوسیستم", "major": "مهندسی کامپیوتر",
        "degree_level": "master", "university_name": "دانشگاه نمونه آریا",
        "engine_mode": "basic", "_maharat_user_id": None,
        "levels": [
            {"skill_code": "python", "skill_name_fa": "پایتون", "category": "برنامه‌نویسی",
             "level": 85.0, "breakdown": [{"title": "مدرک نمونه: نمره درس پایتون پیشرفته ۱۷/۲۰"}]},
            {"skill_code": "data_analysis", "skill_name_fa": "تحلیل داده", "category": "داده",
             "level": 65.0, "breakdown": [{"title": "مدرک نمونه: پروژه تحلیل داده صنعتی"}]},
            {"skill_code": "react", "skill_name_fa": "ری‌اکت", "category": "برنامه‌نویسی",
             "level": 55.0, "breakdown": []},
        ],
    }
    careers = [{"career_id": 1, "career_title": "تحلیلگر داده", "match_score": 43.8,
                "core_missing_count": 1, "engine_mode": "basic"}]
    return profile, careers
