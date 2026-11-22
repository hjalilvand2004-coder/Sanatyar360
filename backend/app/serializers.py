"""Serializer helpers — build API dicts with privacy/access control.

AC-05: بدون رضایت، اطلاعات حساس کاربر برای صنعت نمایش داده نمی‌شود.
"""
from .models import (
    Application, CollaborationProject, Consent, IndustrialProblem, MemberRole,
    OrganizationMembership, User,
)


def user_brief(user: User, full_access: bool = False) -> dict:
    d = {
        "id": user.id,
        "full_name": user.full_name,
        "user_type": user.user_type,
    }
    if full_access:
        d.update({
            "email": user.email,
            "department": user.department,
            "degree": user.degree,
            "bio": user.bio,
        })
    return d


def can_view_full_profile(viewer_memberships: list[OrganizationMembership],
                          target: User, target_consents: list[Consent]) -> bool:
    """Full profile only for university staff or with explicit consent of the owner."""
    roles = {m.role for m in viewer_memberships}
    if roles & {MemberRole.cio_manager, MemberRole.cio_expert, MemberRole.university_admin,
                MemberRole.sys_admin}:
        return True
    granted = any(c.consent_type == "profile_share_industry" and c.granted and not c.revoked_at
                  for c in target_consents)
    return granted


def org_brief(org) -> dict:
    return {
        "id": org.id,
        "name": org.name,
        "org_type": org.org_type.value if hasattr(org.org_type, "value") else org.org_type,
        "industry_sector": org.industry_sector,
        "city": org.city,
        "status": org.status.value if hasattr(org.status, "value") else org.status,
        "logo_hint": org.name[:2],
    }


def problem_brief(p: IndustrialProblem, skill_names: list[str] | None = None) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "summary": p.summary,
        "category": p.category,
        "industry_code": p.industry_code,
        "status": p.status.value if hasattr(p.status, "value") else p.status,
        "confidentiality_level": p.confidentiality_level.value if hasattr(p.confidentiality_level, "value") else p.confidentiality_level,
        "work_mode": p.work_mode.value if hasattr(p.work_mode, "value") else p.work_mode,
        "budget_min": float(p.budget_min) if p.budget_min is not None else None,
        "budget_max": float(p.budget_max) if p.budget_max is not None else None,
        "currency": p.currency,
        "duration_days": p.duration_days,
        "application_deadline": p.application_deadline.isoformat() if p.application_deadline else None,
        "nda_required": p.nda_required,
        "version": p.version,
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
        "owner": org_brief(p.owner),
        "required_skills": skill_names or [rs.skill.name for rs in (p.required_skills or [])],
    }


def problem_detail(p: IndustrialProblem) -> dict:
    d = problem_brief(p)
    d.update({
        "description": p.description,
        "expected_outcomes": p.expected_outcomes,
        "acceptance_criteria": p.acceptance_criteria,
        "required_team_size": p.required_team_size,
        "budget_confirmed": p.budget_confirmed,
        "location": p.location,
        "resources_offered": p.resources_offered,
        "ip_policy_summary": p.ip_policy_summary,
        "desired_start": p.desired_start,
        "contact_name": p.contact_name,
        "contact_channel": p.contact_channel,
        "required_skills_full": [
            {"skill": rs.skill.name, "min_level": rs.min_level, "is_required": rs.is_required}
            for rs in (p.required_skills or [])
        ],
        "rejection_reason": p.rejection_reason,
    })
    return d


def application_brief(a: Application, applicant: User, problem_title: str,
                      full_profile: bool, members: list | None = None) -> dict:
    d = {
        "id": a.id,
        "problem_id": a.problem_id,
        "problem_title": problem_title,
        "applicant": user_brief(applicant, full_access=full_profile),
        "team_name": a.team_name,
        "proposed_role": a.proposed_role,
        "fit_statement": a.fit_statement,
        "weekly_hours": a.weekly_hours,
        "available_from": a.available_from,
        "status": a.status.value if hasattr(a.status, "value") else a.status,
        "decision_reason": a.decision_reason,
        "consent_data_share": a.consent_data_share,
        "profile_limited": not full_profile,
        "created_at": a.created_at.isoformat(),
        "members": members or [],
    }
    if full_profile:
        d["related_background"] = a.related_background
        d["initial_plan"] = a.initial_plan
    return d


def project_brief(p: CollaborationProject) -> dict:
    return {
        "id": p.id,
        "code": p.code,
        "problem_id": p.problem_id,
        "title": p.title,
        "scope": p.scope,
        "status": p.status.value if hasattr(p.status, "value") else p.status,
        "status_note": p.status_note,
        "final_achievement": p.final_achievement,
        "industry_org_id": p.industry_org_id,
        "university_org_id": p.university_org_id,
        "academic_lead_user_id": p.academic_lead_user_id,
        "industry_rep_user_id": p.industry_rep_user_id,
        "agreement_ref": p.agreement_ref,
        "nda_ref": p.nda_ref,
        "external_project_id": p.external_project_id,
        "started_at": p.started_at.isoformat() if p.started_at else None,
        "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        "created_at": p.created_at.isoformat(),
    }
