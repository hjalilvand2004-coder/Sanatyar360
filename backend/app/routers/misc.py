"""ماژول‌های عمومی: اعلان‌ها، حسابرسی، رضایت‌ها، مهارت‌ها، پیوست‌ها، سلامت سامانه."""
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.deps import get_current_user, get_memberships
from ..db import get_db
from ..models import (
    Attachment, AuditLog, Consent, IndustrialProblem, Notification, Skill,
    User, utcnow, IntegrationRun,
)
from ..services import log_audit

router = APIRouter(tags=["misc"])

ALLOWED_EXT = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg",
               ".zip", ".txt", ".csv"}


@router.get("/health")
def health():
    return {"status": "ok", "service": "uiis-api", "version": "v1"}


# ---------- Notifications ----------
@router.get("/notifications")
def notifications(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = db.query(Notification).filter_by(user_id=user.id).order_by(
        Notification.created_at.desc()).limit(100).all()
    unread = db.query(Notification).filter_by(user_id=user.id, is_read=False).count()
    return {"items": [{"id": n.id, "title": n.title, "body": n.body, "link": n.link,
                       "is_read": n.is_read, "created_at": n.created_at.isoformat()}
                      for n in items], "unread": unread}


@router.post("/notifications/{nid}/read")
def mark_read(nid: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    n = db.get(Notification, nid)
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "اعلان یافت نشد"})
    n.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/notifications/read-all")
def mark_all_read(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    db.query(Notification).filter_by(user_id=user.id, is_read=False).update({"is_read": True})
    db.commit()
    return {"ok": True}


# ---------- Audit logs (sys_admin) ----------
@router.get("/audit-logs")
def audit_logs(entity_type: str | None = None, action: str | None = None, limit: int = 200,
               db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    memberships = get_memberships(db, user)
    from ..models import MemberRole
    if not ({m.role for m in memberships} & {MemberRole.sys_admin}):
        raise HTTPException(status_code=403, detail={
            "code": "forbidden", "message": "مشاهده حسابرسی فقط برای مدیر فنی سامانه"})
    query = db.query(AuditLog)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    if action:
        query = query.filter(AuditLog.action == action)
    logs = query.order_by(AuditLog.created_at.desc()).limit(min(limit, 500)).all()
    return {"items": [{
        "id": a.id, "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id,
        "actor": (db.get(User, a.actor_user_id).full_name if a.actor_user_id else "ناشناس"),
        "detail": a.detail, "ip": a.ip, "created_at": a.created_at.isoformat(),
    } for a in logs], "total": len(logs)}


# ---------- Consents ----------
class ConsentIn(BaseModel):
    consent_type: str
    granted: bool


@router.post("/me/consents")
def set_consent(payload: ConsentIn, request: Request, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    if payload.consent_type not in ("profile_share_industry", "data_usage"):
        raise HTTPException(status_code=422, detail={"code": "validation",
                                                     "message": "نوع رضایت نامعتبر است"})
    c = Consent(user_id=user.id, consent_type=payload.consent_type, granted=payload.granted,
                scope_text="اشتراک پروفایل حداقلی (نام، مهارت‌ها، توضیح تناسب) با سازمان مالک مسئله و دفتر ارتباط با صنعت"
                if payload.consent_type == "profile_share_industry" else "استفاده از داده‌های پروفایل در موتور تطبیق")
    if not payload.granted:
        c.revoked_at = utcnow()
    db.add(c)
    log_audit(db, user.id, "consent_changed", "consent", user.id,
              {"type": payload.consent_type, "granted": payload.granted}, request)
    db.commit()
    return {"ok": True}


# ---------- Skills ----------
@router.get("/skills")
def list_skills(q: str | None = None, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    query = db.query(Skill)
    if q:
        query = query.filter(Skill.name.ilike(f"%{q}%"))
    skills = query.limit(100).all()
    return {"items": [{"id": s.id, "name": s.name, "category": s.category} for s in skills]}


class SkillIn(BaseModel):
    name: str
    level: int = 3
    evidence_note: str | None = None


@router.post("/me/skills")
def add_my_skill(payload: SkillIn, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    name = payload.name.strip()
    skill = db.query(Skill).filter(Skill.name == name).first()
    if not skill:
        skill = Skill(name=name)
        db.add(skill)
        db.flush()
    from ..models import UserSkillSnapshot
    row = db.query(UserSkillSnapshot).filter_by(user_id=user.id, skill_id=skill.id).first()
    if row:
        row.level = payload.level
        row.evidence_note = payload.evidence_note
    else:
        db.add(UserSkillSnapshot(user_id=user.id, skill_id=skill.id, level=payload.level,
                                 evidence_note=payload.evidence_note))
    db.commit()
    return {"ok": True}


@router.get("/me/skills")
def my_skills(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from ..models import UserSkillSnapshot
    rows = db.query(UserSkillSnapshot).filter_by(user_id=user.id).all()
    return {"items": [{"skill": r.skill.name, "level": r.level, "source": r.source,
                       "evidence_note": r.evidence_note} for r in rows]}


# ---------- Attachments ----------
@router.post("/attachments")
async def upload_attachment(problem_id: str | None = None, project_id: str | None = None,
                            request: Request = None, file: UploadFile = File(...),
                            db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=422, detail={
            "code": "invalid_file_type", "message": f"نوع فایل «{ext or 'نامشخص'}» مجاز نیست"})
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail={
            "code": "file_too_large",
            "message": f"حداکثر اندازه فایل {settings.max_upload_mb} مگابایت است"})
    os.makedirs(settings.uploads_dir, exist_ok=True)
    key = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(settings.uploads_dir, key), "wb") as f:
        f.write(content)
    if problem_id:
        p = db.get(IndustrialProblem, problem_id)
        if not p:
            raise HTTPException(status_code=404, detail={"code": "not_found",
                                                         "message": "مسئله یافت نشد"})
    a = Attachment(problem_id=problem_id, project_id=project_id, uploader_id=user.id,
                   filename=file.filename, storage_key=key, size_bytes=len(content),
                   content_type=file.content_type, access_level="participants")
    db.add(a)
    log_audit(db, user.id, "file_uploaded", "attachment", a.id,
              {"filename": file.filename, "size": len(content)}, request)
    db.commit()
    return {"id": a.id, "filename": a.filename, "size_bytes": a.size_bytes}


@router.get("/attachments/{att_id}/download")
def download_attachment(att_id: str, db: Session = Depends(get_db),
                        user: User = Depends(get_current_user)):
    from fastapi.responses import FileResponse
    a = db.get(Attachment, att_id)
    if not a:
        raise HTTPException(status_code=404, detail={"code": "not_found",
                                                     "message": "فایل یافت نشد"})
    path = os.path.join(settings.uploads_dir, a.storage_key)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail={"code": "file_missing",
                                                     "message": "فایل در فضای ذخیره‌سازی موجود نیست"})
    return FileResponse(path, filename=a.filename)


# ---------- Integration runs (observability) ----------
@router.get("/integration-runs")
def integration_runs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from ..models import MemberRole
    memberships = get_memberships(db, user)
    if not ({m.role for m in memberships} & {MemberRole.sys_admin}):
        raise HTTPException(status_code=403, detail={"code": "forbidden",
                                                     "message": "دسترسی فقط مدیر فنی"})
    runs = db.query(IntegrationRun).order_by(IntegrationRun.ran_at.desc()).limit(50).all()
    return {"items": [{"id": r.id, "system": r.system_name, "direction": r.direction,
                       "status": r.status, "records": r.records, "note": r.note,
                       "ran_at": r.ran_at.isoformat()} for r in runs]}
