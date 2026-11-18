"""SQLAlchemy models — سامانه تعامل دانشگاه و صنعت (دانشجو۳۶۰)"""
import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import (
    JSON, Boolean, DateTime, Enum as SAEnum, Float, ForeignKey, Integer,
    Numeric, String, Text, UniqueConstraint, Index, TypeDecorator, CHAR,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


def uid() -> str:
    return str(uuid.uuid4())


def as_utc(dt: datetime | None) -> datetime | None:
    """نرمال‌سازی زمان — SQLite زمان naive برمی‌گرداند؛ برای مقایسه امن است."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class GUID(TypeDecorator):
    """UUID سازگار با PostgreSQL و SQLite — به‌صورت CHAR(36) ذخیره می‌شود."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import UUID as PGUIID
            return dialect.type_descriptor(PGUIID(as_uuid=False))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        return value


# ---------- Enums ----------
class OrgType(str, Enum):
    industry = "industry"
    university = "university"


class OrgStatus(str, Enum):
    pending = "pending"          # در انتظار احراز
    verified = "verified"
    rejected = "rejected"
    suspended = "suspended"


class MemberRole(str, Enum):
    industry_rep = "industry_rep"          # نماینده صنعت
    industry_manager = "industry_manager"  # مدیر سازمان صنعتی
    student = "student"
    professor = "professor"
    cio_manager = "cio_manager"            # مدیر دفتر ارتباط با صنعت
    cio_expert = "cio_expert"              # کارشناس حوزه تخصصی / داور
    comm_expert = "comm_expert"            # کارشناس تجاری‌سازی
    university_admin = "university_admin"
    policy_maker = "policy_maker"
    sys_admin = "sys_admin"


class MembershipStatus(str, Enum):
    active = "active"
    pending = "pending"
    revoked = "revoked"


class ProblemStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    under_review = "under_review"
    needs_revision = "needs_revision"
    published = "published"
    applications_closed = "applications_closed"
    converted_to_project = "converted_to_project"
    rejected = "rejected"
    withdrawn = "withdrawn"
    expired = "expired"
    archived = "archived"


class Confidentiality(str, Enum):
    public = "public"
    registered_users = "registered_users"
    selected_participants = "selected_participants"
    confidential = "confidential"


class WorkMode(str, Enum):
    onsite = "onsite"
    remote = "remote"
    hybrid = "hybrid"


class ReviewDecision(str, Enum):
    approve = "approve"
    needs_revision = "needs_revision"
    reject = "reject"


class AppStatus(str, Enum):
    draft = "draft"
    submitted = "submitted"
    under_review = "under_review"
    shortlisted = "shortlisted"
    accepted = "accepted"
    rejected = "rejected"
    withdrawn = "withdrawn"


class TeamMemberStatus(str, Enum):
    invited = "invited"
    accepted = "accepted"
    declined = "declined"


class MatchRunStatus(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class ProjectStatus(str, Enum):
    proposed = "proposed"
    agreement_pending = "agreement_pending"
    active = "active"
    on_hold = "on_hold"
    completed = "completed"
    terminated = "terminated"


class MilestoneStatus(str, Enum):
    pending = "pending"
    done = "done"
    late = "late"
    cancelled = "cancelled"


class DeliverableStatus(str, Enum):
    submitted = "submitted"
    accepted = "accepted"
    revision_requested = "revision_requested"


class CommCaseStatus(str, Enum):
    suggested = "suggested"
    under_expert_review = "under_expert_review"
    expert_approved = "expert_approved"
    rejected = "rejected"
    in_negotiation = "in_negotiation"


# ---------- Identity & Organizations ----------
class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(255))
    user_type: Mapped[str] = mapped_column(String(20), default="student")  # student/professor/industry/staff
    department: Mapped[str | None] = mapped_column(String(150), nullable=True)
    degree: Mapped[str | None] = mapped_column(String(80), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    memberships: Mapped[list["OrganizationMembership"]] = relationship(back_populates="user")


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200), index=True)
    org_type: Mapped[OrgType] = mapped_column(SAEnum(OrgType, name="org_type"))
    legal_id: Mapped[str | None] = mapped_column(String(80), nullable=True)  # شناسه قانونی/ثبت
    industry_sector: Mapped[str | None] = mapped_column(String(120), nullable=True)  # حوزه صنعت
    size: Mapped[str | None] = mapped_column(String(40), nullable=True)  # اندازه سازمان
    city: Mapped[str | None] = mapped_column(String(80), nullable=True)
    website: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[OrgStatus] = mapped_column(SAEnum(OrgStatus, name="org_status"), default=OrgStatus.pending)
    restriction_note: Mapped[str | None] = mapped_column(Text, nullable=True)  # تعلیق/محدودیت همکاری
    created_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (Index("ix_orgs_type_status", "org_type", "status"),)


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), index=True)
    organization_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.id"), index=True)
    role: Mapped[MemberRole] = mapped_column(SAEnum(MemberRole, name="member_role"))
    status: Mapped[MembershipStatus] = mapped_column(
        SAEnum(MembershipStatus, name="membership_status"), default=MembershipStatus.active)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "organization_id", "role", name="uq_membership"),)

    user: Mapped[User] = relationship(back_populates="memberships")
    organization: Mapped[Organization] = relationship()


class OrganizationVerification(Base):
    __tablename__ = "organization_verifications"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.id"), index=True)
    requested_by: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"))
    documents_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending/approved/rejected
    reviewed_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# ---------- Skills & profile snapshots ----------
class Skill(Base):
    __tablename__ = "skills"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)  # نرمال‌شده
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)


class UserSkillSnapshot(Base):
    __tablename__ = "user_skill_snapshots"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), index=True)
    skill_id: Mapped[str] = mapped_column(GUID(), ForeignKey("skills.id"), index=True)
    level: Mapped[int] = mapped_column(Integer, default=3)  # 1..5
    evidence_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(30), default="self_declared")  # self_declared/verified/imported
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "skill_id", name="uq_user_skill"),)

    skill: Mapped[Skill] = relationship()


# ---------- Industrial problems ----------
class IndustrialProblem(Base):
    __tablename__ = "industrial_problems"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    owner_organization_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.id"), index=True)
    title: Mapped[str] = mapped_column(String(250))
    summary: Mapped[str] = mapped_column(Text)                       # خلاصه عمومی (برای سطوح محرمانه)
    description: Mapped[str] = mapped_column(Text)                   # شرح کامل
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    industry_code: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)
    expected_outcomes: Mapped[list | None] = mapped_column(JSON, nullable=True)    # تحویل‌دادنی‌ها
    acceptance_criteria: Mapped[list | None] = mapped_column(JSON, nullable=True)  # معیار پذیرش
    required_team_size: Mapped[int] = mapped_column(Integer, default=2)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    budget_min: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    budget_max: Mapped[float | None] = mapped_column(Numeric(16, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="IRR")
    budget_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)  # قطعیت بودجه
    work_mode: Mapped[WorkMode] = mapped_column(SAEnum(WorkMode, name="work_mode"), default=WorkMode.hybrid)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    resources_offered: Mapped[str | None] = mapped_column(Text, nullable=True)  # تجهیزات/داده قابل ارائه
    confidentiality_level: Mapped[Confidentiality] = mapped_column(
        SAEnum(Confidentiality, name="confidentiality"), default=Confidentiality.public)
    ip_policy_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    nda_required: Mapped[bool] = mapped_column(Boolean, default=False)
    application_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    desired_start: Mapped[str | None] = mapped_column(String(40), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_channel: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[ProblemStatus] = mapped_column(
        SAEnum(ProblemStatus, name="problem_status"), default=ProblemStatus.draft, index=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    __table_args__ = (
        Index("ix_problems_org_status", "owner_organization_id", "status"),
        Index("ix_problems_status_deadline", "status", "application_deadline"),
    )

    owner: Mapped[Organization] = relationship()
    required_skills: Mapped[list["ProblemRequiredSkill"]] = relationship(
        back_populates="problem", cascade="all, delete-orphan")


class ProblemVersion(Base):
    __tablename__ = "problem_versions"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    problem_id: Mapped[str] = mapped_column(GUID(), ForeignKey("industrial_problems.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    changed_by: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProblemRequiredSkill(Base):
    __tablename__ = "problem_required_skills"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    problem_id: Mapped[str] = mapped_column(GUID(), ForeignKey("industrial_problems.id"), index=True)
    skill_id: Mapped[str] = mapped_column(GUID(), ForeignKey("skills.id"), index=True)
    min_level: Mapped[int] = mapped_column(Integer, default=2)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("problem_id", "skill_id", name="uq_problem_skill"),)

    problem: Mapped[IndustrialProblem] = relationship(back_populates="required_skills")
    skill: Mapped[Skill] = relationship()


class ProblemReview(Base):
    __tablename__ = "problem_reviews"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    problem_id: Mapped[str] = mapped_column(GUID(), ForeignKey("industrial_problems.id"), index=True)
    reviewer_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"))
    decision: Mapped[ReviewDecision] = mapped_column(SAEnum(ReviewDecision, name="review_decision"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProblemQuestion(Base):
    __tablename__ = "problem_questions"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    problem_id: Mapped[str] = mapped_column(GUID(), ForeignKey("industrial_problems.id"), index=True)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answered_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProblemInterest(Base):
    __tablename__ = "problem_interests"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    problem_id: Mapped[str] = mapped_column(GUID(), ForeignKey("industrial_problems.id"), index=True)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("problem_id", "user_id", name="uq_problem_interest"),)


# ---------- Applications ----------
class Application(Base):
    __tablename__ = "applications"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    problem_id: Mapped[str] = mapped_column(GUID(), ForeignKey("industrial_problems.id"), index=True)
    applicant_user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), index=True)
    team_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    proposed_role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    fit_statement: Mapped[str] = mapped_column(Text)          # توضیح تناسب
    related_background: Mapped[str | None] = mapped_column(Text, nullable=True)
    weekly_hours: Mapped[int] = mapped_column(Integer, default=10)
    available_from: Mapped[str | None] = mapped_column(String(40), nullable=True)
    initial_plan: Mapped[str | None] = mapped_column(Text, nullable=True)  # طرح اولیه حل
    consent_data_share: Mapped[bool] = mapped_column(Boolean, default=False)  # رضایت اشتراک اطلاعات
    status: Mapped[AppStatus] = mapped_column(
        SAEnum(AppStatus, name="app_status"), default=AppStatus.submitted, index=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    __table_args__ = (UniqueConstraint("problem_id", "applicant_user_id", name="uq_application"),)


class ApplicationMember(Base):
    __tablename__ = "application_members"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    application_id: Mapped[str] = mapped_column(GUID(), ForeignKey("applications.id"), index=True)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"))
    role: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[TeamMemberStatus] = mapped_column(
        SAEnum(TeamMemberStatus, name="team_member_status"), default=TeamMemberStatus.invited)


# ---------- Matching ----------
class MatchRun(Base):
    __tablename__ = "match_runs"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    problem_id: Mapped[str] = mapped_column(GUID(), ForeignKey("industrial_problems.id"), index=True)
    algorithm_version: Mapped[str] = mapped_column(String(40), default="rules-v1.0")
    status: Mapped[MatchRunStatus] = mapped_column(
        SAEnum(MatchRunStatus, name="match_run_status"), default=MatchRunStatus.completed)
    weights: Mapped[dict] = mapped_column(JSON, default=dict)
    stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MatchResult(Base):
    __tablename__ = "match_results"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    match_run_id: Mapped[str] = mapped_column(GUID(), ForeignKey("match_runs.id"), index=True)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    reasons: Mapped[list] = mapped_column(JSON, default=list)   # عوامل مؤثر
    missing: Mapped[list] = mapped_column(JSON, default=list)   # کمبودها
    data_quality_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------- Collaborations ----------
class CollaborationProject(Base):
    __tablename__ = "collaboration_projects"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    code: Mapped[str] = mapped_column(String(30), unique=True, default=lambda: f"COL-{uuid.uuid4().hex[:8].upper()}")
    problem_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("industrial_problems.id"), index=True, nullable=True)
    application_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("applications.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(250))
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)            # محدوده کار
    acceptance_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry_org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.id"), index=True)
    university_org_id: Mapped[str] = mapped_column(GUID(), ForeignKey("organizations.id"), index=True)
    academic_lead_user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"))
    industry_rep_user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"))
    external_project_id: Mapped[str | None] = mapped_column(String(80), nullable=True)  # شناسه در سامانه مدیریت پروژه
    agreement_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    nda_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        SAEnum(ProjectStatus, name="project_status"), default=ProjectStatus.agreement_pending, index=True)
    status_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    final_achievement: Mapped[str | None] = mapped_column(Text, nullable=True)  # دستاورد نهایی
    dispute_note: Mapped[str | None] = mapped_column(Text, nullable=True)       # اختلاف
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ProjectMember(Base):
    __tablename__ = "project_members"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(GUID(), ForeignKey("collaboration_projects.id"), index=True)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), index=True)
    organization_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("organizations.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(80))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("project_id", "user_id", "role", name="uq_project_member"),)

    user: Mapped[User] = relationship()


class ProjectMilestone(Base):
    __tablename__ = "project_milestones"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(GUID(), ForeignKey("collaboration_projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    due_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[MilestoneStatus] = mapped_column(
        SAEnum(MilestoneStatus, name="milestone_status"), default=MilestoneStatus.pending)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Deliverable(Base):
    __tablename__ = "deliverables"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(GUID(), ForeignKey("collaboration_projects.id"), index=True)
    milestone_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("project_milestones.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[DeliverableStatus] = mapped_column(
        SAEnum(DeliverableStatus, name="deliverable_status"), default=DeliverableStatus.submitted)
    submitted_by: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    reviewed_by: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgreementReference(Base):
    __tablename__ = "agreement_references"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(GUID(), ForeignKey("collaboration_projects.id"), index=True)
    ref_type: Mapped[str] = mapped_column(String(20))  # contract / nda
    reference_code: Mapped[str] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CollaborationEvaluation(Base):
    __tablename__ = "collaboration_evaluations"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    project_id: Mapped[str] = mapped_column(GUID(), ForeignKey("collaboration_projects.id"), index=True)
    evaluator_user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"))
    rating: Mapped[int] = mapped_column(Integer)  # 1..5
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("project_id", "evaluator_user_id", name="uq_evaluation"),)


# ---------- Market data / skill demand ----------
class MarketDataSource(Base):
    __tablename__ = "market_data_sources"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(60))  # job_ads/survey/official_report/internal
    url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    license_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    coverage_note: Mapped[str | None] = mapped_column(Text, nullable=True)  # شرایط و پوشش استفاده
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MarketObservation(Base):
    __tablename__ = "market_observations"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    source_id: Mapped[str] = mapped_column(GUID(), ForeignKey("market_data_sources.id"), index=True)
    skill_raw: Mapped[str] = mapped_column(String(150))
    skill_id: Mapped[str] = mapped_column(GUID(), ForeignKey("skills.id"), index=True)
    industry_code: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)
    region: Mapped[str | None] = mapped_column(String(80), nullable=True)
    demand_count: Mapped[int] = mapped_column(Integer, default=0)
    observed_month: Mapped[str] = mapped_column(String(7), index=True)  # YYYY-MM
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------- Commercialization ----------
class ResearchAssetSnapshot(Base):
    __tablename__ = "research_asset_snapshots"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    external_research_id: Mapped[str | None] = mapped_column(String(80), nullable=True)  # شناسه در سامانه پژوهش
    title: Mapped[str] = mapped_column(String(250))
    asset_type: Mapped[str] = mapped_column(String(40), default="paper")  # paper/patent/prototype
    owner_user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    trl_level: Mapped[int | None] = mapped_column(Integer, nullable=True)  # مرحله توسعه 1..9
    application_fields: Mapped[list | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)   # شواهد آزمون
    ip_status: Mapped[str | None] = mapped_column(String(80), nullable=True)  # وضعیت مالکیت فکری
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommercializationCase(Base):
    __tablename__ = "commercialization_cases"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    research_asset_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("research_asset_snapshots.id"), nullable=True)
    related_problem_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("industrial_problems.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(250))
    rationale: Mapped[str] = mapped_column(Text)          # دلیل پیشنهاد (با ارجاع شواهد)
    application_fields: Mapped[list | None] = mapped_column(JSON, nullable=True)
    evidence: Mapped[list | None] = mapped_column(JSON, nullable=True)   # [{claim, source, kind: explicit/inference}]
    uncertainties: Mapped[str | None] = mapped_column(Text, nullable=True)  # ابهامات و داده ناقص
    market_signal: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"))
    status: Mapped[CommCaseStatus] = mapped_column(
        SAEnum(CommCaseStatus, name="comm_case_status"), default=CommCaseStatus.suggested, index=True)
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommercializationReview(Base):
    __tablename__ = "commercialization_reviews"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    case_id: Mapped[str] = mapped_column(GUID(), ForeignKey("commercialization_cases.id"), index=True)
    expert_user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"))
    need_fit_score: Mapped[int | None] = mapped_column(Integer, nullable=True)   # تناسب با نیاز واقعی 1..5
    trl_assessment: Mapped[int | None] = mapped_column(Integer, nullable=True)
    market_evidence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    decision: Mapped[str] = mapped_column(String(30), default="proceed")  # proceed/reject/need_info
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------- Platform ----------
class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    problem_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("industrial_problems.id"), nullable=True)
    project_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("collaboration_projects.id"), nullable=True)
    uploader_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"))
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(255), unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    access_level: Mapped[str] = mapped_column(String(30), default="participants")  # public/participants/reviewers
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), index=True)
    consent_type: Mapped[str] = mapped_column(String(60))  # profile_share_industry / data_usage
    granted: Mapped[bool] = mapped_column(Boolean, default=False)
    scope_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    link: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    actor_user_id: Mapped[str | None] = mapped_column(GUID(), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(60))
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class OutboxEvent(Base):
    __tablename__ = "outbox_events"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    external_system: Mapped[str | None] = mapped_column(String(60), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(150), unique=True, nullable=True)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IntegrationRun(Base):
    __tablename__ = "integration_runs"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    system_name: Mapped[str] = mapped_column(String(60))
    direction: Mapped[str] = mapped_column(String(20))  # import/export
    status: Mapped[str] = mapped_column(String(20), default="ok")  # ok/failed/partial
    records: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MaharatLink(Base):
    """پیوند پروفایل مهارتی کاربر با زیرسیستم مهارتیار۳۶۰ (اکوسیستم دانشجویار۳۶۰).

    فقط سطوح مهارتی تأییدشده و خلاصه شواهد ذخیره می‌شود؛ هیچ اعتبارنامه‌ای از
    مهارتیار نگهداری نمی‌شود. رضایت کاربر با ثبت خودِ پیوند اعمال می‌گردد.
    """
    __tablename__ = "maharat_links"
    id: Mapped[str] = mapped_column(GUID(), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(GUID(), ForeignKey("users.id"), unique=True, index=True)
    maharat_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maharat_profile_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maharat_full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    major: Mapped[str | None] = mapped_column(String(120), nullable=True)
    degree_level: Mapped[str | None] = mapped_column(String(40), nullable=True)
    university_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    engine_mode: Mapped[str | None] = mapped_column(String(30), nullable=True)
    levels_json: Mapped[list | None] = mapped_column(JSON, nullable=True)   # [{skill_code, skill_name_fa, name_en, aliases, category, level, evidence_count, top_evidence}]
    careers_json: Mapped[list | None] = mapped_column(JSON, nullable=True)  # [{career_id, career_title, match_score, core_missing_count}]
    skills_total: Mapped[int] = mapped_column(Integer, default=0)
    verified_evidences: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str] = mapped_column(String(30), default="service_admin")  # service_admin/self_token/seed_sample
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)  # داده نمونه در نبود دسترسی
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    refreshed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship()
