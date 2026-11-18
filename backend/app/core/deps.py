"""Auth dependencies and RBAC helpers.

مجوز = ترکیب نقش + سازمان + عضویت در پروژه + سطح محرمانگی.
"""
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import MemberRole, MembershipStatus, Organization, OrganizationMembership, User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(request: Request, db: Session = Depends(get_db),
                     creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> User:
    if creds is None:
        raise HTTPException(status_code=401, detail={"code": "unauthenticated",
                                                     "message": "احراز هویت لازم است"})
    user_id = decode_token(creds.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail={"code": "invalid_token",
                                                     "message": "توکن نامعتبر یا منقضی است"})
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail={"code": "inactive",
                                                     "message": "کاربر غیرفعال است"})
    return user


def get_memberships(db: Session, user: User) -> list[OrganizationMembership]:
    return (db.query(OrganizationMembership)
            .filter(OrganizationMembership.user_id == user.id,
                    OrganizationMembership.status == MembershipStatus.active)
            .all())


def user_roles(memberships: list[OrganizationMembership]) -> set[MemberRole]:
    return {m.role for m in memberships}


def require_roles(user: User, memberships: list[OrganizationMembership], *roles: MemberRole):
    """Global role check (org-agnostic)."""
    if not (user_roles(memberships) & set(roles)):
        raise HTTPException(status_code=403, detail={
            "code": "forbidden",
            "message": "نقش شما برای این عملیات مجاز نیست",
            "required_roles": [r.value for r in roles],
        })


def require_org_role(user: User, memberships: list[OrganizationMembership],
                     org_id: str, *roles: MemberRole):
    """Role check scoped to a specific organization."""
    ok = any(m.organization_id == org_id and m.role in roles for m in memberships)
    if not ok:
        raise HTTPException(status_code=403, detail={
            "code": "forbidden_org_scope",
            "message": "این عملیات فقط برای نقش‌های مجاز در همان سازمان امکان‌پذیر است",
        })


def university_staff_orgs(memberships: list[OrganizationMembership]) -> list[str]:
    """Org ids (university side) where the user has CIO-office / admin roles."""
    return [m.organization_id for m in memberships if m.role in {
        MemberRole.cio_manager, MemberRole.cio_expert, MemberRole.university_admin}]


def is_university_staff(memberships: list[OrganizationMembership]) -> bool:
    return bool(user_roles(memberships) & {
        MemberRole.cio_manager, MemberRole.cio_expert, MemberRole.university_admin,
        MemberRole.comm_expert, MemberRole.sys_admin})
