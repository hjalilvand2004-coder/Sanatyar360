"""Audit log, notification and outbox helpers."""
from fastapi import Request
from sqlalchemy.orm import Session

from ..models import AuditLog, Notification, OutboxEvent, utcnow


def log_audit(db: Session, actor_id: str | None, action: str, entity_type: str,
              entity_id: str | None = None, detail: dict | None = None,
              request: Request | None = None):
    ip = None
    if request is not None:
        ip = request.client.host if request.client else request.headers.get("x-forwarded-for")
    db.add(AuditLog(actor_user_id=actor_id, action=action, entity_type=entity_type,
                    entity_id=entity_id, detail=detail, ip=ip))


def notify(db: Session, user_id: str, title: str, body: str | None = None, link: str | None = None):
    if user_id:
        db.add(Notification(user_id=user_id, title=title, body=body, link=link))


def add_outbox(db: Session, event_type: str, payload: dict, external_system: str | None = None,
               dedupe_key: str | None = None):
    db.add(OutboxEvent(event_type=event_type, payload=payload,
                       external_system=external_system, dedupe_key=dedupe_key))
