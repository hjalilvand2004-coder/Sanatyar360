"""APIهای یکپارچگی با مهارتیار۳۶۰ — پیوند پروفایل، واژه‌نامه، شکاف مهارتی."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core.deps import get_current_user
from ..db import get_db
from ..models import MaharatLink, User, utcnow
from ..services import log_audit, maharat as M

router = APIRouter(tags=["maharat"])


def _link_or_404(db: Session, user_id: str) -> MaharatLink:
    link = db.query(MaharatLink).filter_by(user_id=user_id).first()
    if not link:
        raise HTTPException(status_code=404, detail={
            "code": "not_linked",
            "message": "پروفایل شما به مهارت‌یار۳۶۰ پیوند خورده نیست؛ ابتدا از صفحه «مهارت‌یار۳۶۰» پیوند بزنید"})
    return link


def _link_payload(link: MaharatLink) -> dict:
    return {
        "linked": True,
        "maharat_full_name": link.maharat_full_name,
        "major": link.major,
        "degree_level": link.degree_level,
        "university_name": link.university_name,
        "engine_mode": link.engine_mode,
        "skills_total": link.skills_total,
        "verified_evidences": link.verified_evidences,
        "levels": link.levels_json or [],
        "careers": link.careers_json or [],
        "source": link.source,
        "is_sample": link.is_sample,
        "linked_at": link.linked_at.isoformat(),
        "refreshed_at": link.refreshed_at.isoformat(),
    }


@router.get("/maharat/status")
def maharat_status(db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """وضعیت ارتباط با زیرسیستم مهارت‌یار۳۶۰ + آمار پیوندها (برای تحلیل/مدیریت)."""
    st = M.status()
    linked = db.query(MaharatLink).count()
    st["linked_users"] = linked
    return st


@router.get("/maharat/skills")
def maharat_skills(user: User = Depends(get_current_user)):
    """واژه‌نامه مهارت مهارتیار۳۶۰ (کد، نام، مترادف‌ها، دسته) — کش ۲۴ساعته."""
    d = M.dictionary(force=True)
    if not d:
        return {"mode": "offline", "items": [],
                "note": "واژه‌نامه در دسترس نیست؛ تطبیق مهارت با واژه‌نامه محلی انجام می‌شود"}
    return {"mode": "live", "items": d["skills"], "fetched_at": d["fetched_at"]}


@router.get("/maharat/careers")
def maharat_careers(user: User = Depends(get_current_user)):
    """فهرست شغل‌های مرجع مهارتیار۳۶۰ (برای رده‌بندی مسائل و تحلیل)."""
    d = M.dictionary(force=True)
    items = (d or {}).get("careers", [])
    return {"mode": "live" if d else "offline", "items": items}


@router.get("/maharat/me")
def my_maharat_profile(db: Session = Depends(get_db),
                       user: User = Depends(get_current_user)):
    link = db.query(MaharatLink).filter_by(user_id=user.id).first()
    if not link:
        return {"linked": False,
                "note": "برای نمایش پروفایل مهارتی تأییدشده، پیوند با مهارت‌یار۳۶۰ برقرار کنید"}
    return _link_payload(link)


class LinkBody(BaseModel):
    email: str | None = Field(default=None, description="ایمیل حساب مهارت‌یار (پیش‌فرض: ایمیل خودتان)")
    token: str | None = Field(default=None, description="توکن دسترسی مهارت‌یار (بدون ذخیره‌سازی)")


@router.post("/maharat/link")
def link_maharat(body: LinkBody | None = None, request: Request = None,
                 db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    """پیوند پروفایل مهارت‌یار۳۶۰ به حساب صنعت‌یار — با رضایت خود کاربر.

    دو مسیر: (۱) جست‌وجوی حساب مهارت‌یار با ایمیل از طریق حساب سرویس؛
    (۲) توکن دسترسی خودِ کاربر که فقط یک‌بار برای واکشی استفاده و ذخیره نمی‌شود.
    """
    if user.user_type not in ("student", "professor"):
        raise HTTPException(status_code=403, detail={
            "code": "forbidden", "message": "پیوند مهارتی فقط برای دانشجو و استاد است"})
    body = body or LinkBody()
    try:
        if body.token:
            link = M.link_by_token(db, user.id, body.token.strip())
        else:
            email = (body.email or user.email).strip()
            link = M.link_by_email(db, user.id, email)
            if not link:
                raise HTTPException(status_code=404, detail={
                    "code": "profile_not_found",
                    "message": "حساب دانشجویی با این ایمیل در مهارت‌یار۳۶۰ یافت نشد؛ "
                               "ایمیل باید با حساب دانشجویی مهارت‌یار یکی باشد یا از توکن استفاده کنید"})
        if request is not None:
            log_audit(db, user.id, "maharat_link_created", "maharat_link", link.id,
                      {"source": link.source, "profile_id": link.maharat_profile_id}, request)
        db.commit()
        return _link_payload(link)
    except M.MaharatUnavailable as e:
        raise HTTPException(status_code=503, detail={
            "code": "maharat_unavailable",
            "message": f"مهارت‌یار۳۶۰ در دسترس نیست؛ بعداً تلاش کنید ({e})"})


@router.post("/maharat/link/refresh")
def refresh_maharat_link(request: Request = None, db: Session = Depends(get_db),
                         user: User = Depends(get_current_user)):
    link = _link_or_404(db, user.id)
    ok = M.refresh_link(db, link)
    db.commit()
    if not ok:
        return {"refreshed": False, **_link_payload(link),
                "note": "به‌روزرسانی از مهارت‌یار ممکن نشد؛ آخرین snapshot حفظ شد"}
    log_audit(db, user.id, "maharat_link_refreshed", "maharat_link", link.id, None, request)
    return {"refreshed": True, **_link_payload(link)}


@router.delete("/maharat/link")
def unlink_maharat(request: Request = None, db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """قطع پیوند — همه داده‌های مهارتیار بلافاصله حذف می‌شود."""
    link = db.query(MaharatLink).filter_by(user_id=user.id).first()
    if not link:
        raise HTTPException(status_code=404, detail={
            "code": "not_linked", "message": "پیوندی وجود ندارد"})
    db.delete(link)
    log_audit(db, user.id, "maharat_link_deleted", "maharat_link", link.id, None, request)
    db.commit()
    return {"linked": False, "message": "پیوند با مهارت‌یار۳۶۰ قطع و داده‌ها حذف شد"}


@router.get("/maharat/skill-gap/{problem_id}")
def maharat_skill_gap(problem_id: str, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    """شکاف مهارتی من نسبت به مهارت‌های الزامی این مسئله — بر مبنای مهارت‌یار۳۶۰."""
    from ..models import IndustrialProblem
    p = db.get(IndustrialProblem, problem_id)
    if not p:
        raise HTTPException(status_code=404, detail={
            "code": "not_found", "message": "مسئله یافت نشد"})
    link = db.query(MaharatLink).filter_by(user_id=user.id).first()
    if not link:
        return {"linked": False,
                "note": "برای تحلیل شکاف مهارتی، پروفایل مهارت‌یار۳۶۰ را پیوند بزنید"}
    out = M.skill_gap_for_problem(db, p, link)
    out["linked"] = True
    out["is_sample"] = link.is_sample
    return out
