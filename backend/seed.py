"""داده‌های نمونه برای راه‌اندازی MVP — کاربران آزمایشی با رمز uiis1234"""
import sys
from datetime import timedelta

from app.core.security import hash_password
from app.db import Base, SessionLocal, engine
from app.models import (
    Application, ApplicationMember, CollaborationEvaluation, CollaborationProject,
    AgreementReference, CommercializationCase, Consent, Deliverable,
    DeliverableStatus, IndustrialProblem, IntegrationRun, MarketDataSource,
    MarketObservation, MatchResult, MatchRun, MemberRole, MembershipStatus,
    Notification, Organization, OrganizationMembership, OrganizationVerification,
    ProblemRequiredSkill, ProblemReview, ProblemStatus, ProblemVersion,
    ProjectMember, ProjectMilestone, ProjectStatus, ReviewDecision, Skill,
    TeamMemberStatus, User, UserSkillSnapshot, utcnow, WorkMode,
    Confidentiality, CommCaseStatus,
)

PASSWORD = "uiis1234"


def main(reset: bool = False):
    if reset:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    if db.query(User).count() > 0:
        print("Seed skipped — data already exists.")
        return

    pw = hash_password(PASSWORD)

    # ---------- سازمان‌ها ----------
    uni = Organization(name="دانشگاه صنعتی نوآوران", org_type="university",
                       legal_id="UNI-1001", city="تهران", website="https://nav.ac.ir",
                       status="verified", description="دانشگاه صنعتی نمونه با گروه‌های مهندسی صنایع و کامپیوتر")
    parstekhno = Organization(name="پارس‌تکنو صنعت", org_type="industry",
                              legal_id="CR-45871", industry_sector="ماشین‌سازی و اتوماسیون",
                              size="۲۰۰ تا ۵۰۰ نفر", city="تهران", website="https://pars-techno.example.ir",
                              contact_name="رضا محمدی", contact_email="rep@pastechno.ir",
                              status="verified",
                              description="تولیدکننده خطوط بسته‌بندی و اتوماسیون صنعتی")
    fezla = Organization(name="فلزآوران اصفهان", org_type="industry", legal_id="CR-77812",
                         industry_sector="فلزات", size="۵۰ تا ۲۰۰ نفر", city="اصفهان",
                         contact_name="علی نوری", contact_email="rep@fezlavaran.ir",
                         status="pending", description="کارخانه فولاد و پروفیل فلزی")
    db.add_all([uni, parstekhno, fezla])
    db.flush()

    # ---------- کاربران ----------
    def add_user(email, name, utype, dept=None, degree=None):
        u = User(email=email, full_name=name, password_hash=pw, user_type=utype,
                 department=dept, degree=degree, is_active=True)
        db.add(u)
        db.flush()
        return u

    rep = add_user("rep@pastechno.ir", "رضا محمدی", "industry")
    mgr = add_user("manager@pastechno.ir", "سارا کریمی", "industry")
    rep2 = add_user("rep@fezlavaran.ir", "علی نوری", "industry")
    prof1 = add_user("prof.hosseini@nav.ac.ir", "دکتر مریم حسینی", "professor",
                     "مهندسی صنایع", "دانشیار")
    prof2 = add_user("prof.karimi@nav.ac.ir", "دکتر حسن کریمی", "professor",
                     "مهندسی کامپیوتر", "استاد")
    st1 = add_user("st1@nav.ac.ir", "امیر رضایی", "student", "مهندسی صنایع", "کارشناسی ارشد")
    st2 = add_user("st2@nav.ac.ir", "نگار صادقی", "student", "مهندسی کامپیوتر", "کارشناسی ارشد")
    st3 = add_user("st3@nav.ac.ir", "سینا عباسی", "student", "مهندسی صنایع", "کارشناسی ارشد")
    cio = add_user("cio@nav.ac.ir", "دکتر لیلا احمدی", "staff")
    expert = add_user("expert@nav.ac.ir", "دکتر فرهاد قاسمی", "staff")
    comm = add_user("comm@nav.ac.ir", "زهرا موسوی", "staff")
    uniadmin = add_user("uniadmin@nav.ac.ir", "دکتر محمود رستمی", "staff")
    policy = add_user("policymaker@msrt.example.ir", "مهندس شیرین نادری", "staff")
    sysadmin = add_user("sysadmin@uiis-system.ir", "مدیر فنی سامانه", "staff")

    memberships = [
        (rep, parstekhno, MemberRole.industry_rep), (rep, parstekhno, MemberRole.industry_manager),
        (mgr, parstekhno, MemberRole.industry_manager),
        (rep2, fezla, MemberRole.industry_rep),
        (prof1, uni, MemberRole.professor), (prof2, uni, MemberRole.professor),
        (st1, uni, MemberRole.student), (st2, uni, MemberRole.student),
        (st3, uni, MemberRole.student),
        (cio, uni, MemberRole.cio_manager), (expert, uni, MemberRole.cio_expert),
        (comm, uni, MemberRole.comm_expert), (uniadmin, uni, MemberRole.university_admin),
        (policy, uni, MemberRole.policy_maker), (sysadmin, uni, MemberRole.sys_admin),
    ]
    for u, o, r in memberships:
        db.add(OrganizationMembership(user_id=u.id, organization_id=o.id, role=r,
                                      status=MembershipStatus.active))
    db.add(OrganizationVerification(organization_id=parstekhno.id, requested_by=rep.id,
                                    status="approved", documents_note="روزنامه رسمی و جواز کسب",
                                    review_note="مستندات کامل بود", reviewed_by=cio.id,
                                    reviewed_at=utcnow() - timedelta(days=10)))
    db.add(OrganizationVerification(organization_id=fezla.id, requested_by=rep2.id,
                                    status="pending", documents_note="در انتظار ارائه روزنامه رسمی"))

    # ---------- مهارت‌ها ----------
    skill_names = ["Python", "تحلیل داده", "یادگیری ماشین", "بینایی ماشین", "یادگیری عمیق",
                   "مهندسی صنایع", "IoT", "داشبوردسازی", "پردازش سیگنال", "شبیه‌سازی"]
    skills = {}
    for s in skill_names:
        sk = Skill(name=s, category="فنی")
        db.add(sk)
        db.flush()
        skills[s] = sk

    def add_skill(u, sname, level, source="self_declared", note=None):
        db.add(UserSkillSnapshot(user_id=u.id, skill_id=skills[sname].id, level=level,
                                 source=source, evidence_note=note))

    add_skill(st1, "Python", 4, "verified", "گواهی دوره + پروژه درس")
    add_skill(st1, "تحلیل داده", 4, "verified")
    add_skill(st1, "مهندسی صنایع", 3)
    add_skill(st1, "شبیه‌سازی", 3)
    add_skill(st2, "Python", 5, "verified", "دو سال تجربه پروژه")
    add_skill(st2, "یادگیری عمیق", 4, "verified")
    add_skill(st2, "بینایی ماشین", 4)
    add_skill(st2, "داشبوردسازی", 3)
    add_skill(st3, "تحلیل داده", 3)
    add_skill(st3, "مهندسی صنایع", 4, "verified")
    add_skill(st3, "IoT", 3)
    add_skill(prof1, "مهندسی صنایع", 5, "verified", "۱۲ مقاله و ۳ طرح صنعتی")
    add_skill(prof1, "یادگیری ماشین", 4, "verified")
    add_skill(prof1, "شبیه‌سازی", 4)
    add_skill(prof2, "بینایی ماشین", 5, "verified")
    add_skill(prof2, "یادگیری عمیق", 5, "verified")
    add_skill(prof2, "Python", 5, "verified")
    add_skill(prof2, "پردازش سیگنال", 4)

    # رضایت دانشجو ۱ برای اشتراک پروفایل
    db.add(Consent(user_id=st1.id, consent_type="profile_share_industry", granted=True,
                   scope_text="اشتراک پروفایل حداقلی با سازمان مالک مسئله و دفتر ارتباط با صنعت"))

    now = utcnow()

    # ---------- مسائل صنعتی ----------
    p1 = IndustrialProblem(
        owner_organization_id=parstekhno.id, title="بهینه‌سازی مصرف انرژی خط تولید بسته‌بندی",
        summary="کاهش ۱۵ درصدی مصرف انرژی خط بسته‌بندی با تحلیل داده و برنامه بهینه‌سازی.",
        description=("خط بسته‌بندی کارخانه در نوبت‌های شبانه مصرف انرژی غیربهینه دارد. "
                     "نیاز به تحلیل داده‌های برق و سنسورها، مدل‌سازی رفتار دستگاه‌ها و "
                     "ارائه برنامه بهینه‌سازی عملیاتی داریم. داده شش ماه گذشته آماده تحویل است."),
        category="انرژی و بهره‌وری", industry_code="MAN-01",
        expected_outcomes=["گزارش تحلیل مصرف انرژی", "مدل پیش‌بینی مصرف", "برنامه بهینه‌سازی عملیاتی"],
        acceptance_criteria=["کاهش شبیه‌سازی‌شده ≥۱۰٪", "تأیید واحد انرژی کارخانه", "مستندسازی مدل"],
        required_team_size=3, duration_days=120, budget_min=300_000_000, budget_max=500_000_000,
        budget_confirmed=True, work_mode="hybrid", location="تهران — کارخانه شماره ۲",
        resources_offered="دسترسی به داده سنسورها و جلسات ماهانه با سرپرست خط",
        confidentiality_level="public", ip_policy_summary="مالکیت خروجی مشترک؛ انتقال دانش به کارخانه",
        application_deadline=now + timedelta(days=30), desired_start="۱۴۰۵/۱۰",
        contact_name="رضا محمدی", contact_channel="ایمیل از طریق سامانه",
        status="published", created_by=rep.id)
    db.add(p1)
    db.flush()
    for s in ["تحلیل داده", "یادگیری ماشین", "Python"]:
        db.add(ProblemRequiredSkill(problem_id=p1.id, skill_id=skills[s].id, min_level=3))
    db.add(ProblemVersion(problem_id=p1.id, version=1, payload={"title": p1.title}, changed_by=rep.id))

    p2 = IndustrialProblem(
        owner_organization_id=parstekhno.id, title="سیستم بینایی ماشین برای بازرسی کیفیت قطعات",
        summary="طراحی سامانه بینایی ماشین برای تشخیص عیوب سطحی قطعات فلزی روی خط.",
        description=("اسناد فنی محرمانه شامل نقشه خط و نمونه داده تصویری است. "
                     "هدف: تشخیص خودکار عیوب سطحی با دقت بالای ۹۵٪ و یکپارچه‌سازی با MES."),
        category="اتوماسیون و کنترل کیفیت", industry_code="MAN-01",
        expected_outcomes=["نمونه اولیه سامانه بینایی", "مستندات آموزش مدل", "گزارش دقت"],
        acceptance_criteria=["دقت ≥۹۵٪ روی داده آزمون", "زمان پردازش < ۵۰۰ms به‌ازای قطعه"],
        required_team_size=2, duration_days=150, budget_min=400_000_000, budget_max=600_000_000,
        work_mode="hybrid", location="تهران",
        confidentiality_level="registered_users", nda_required=True,
        ip_policy_summary="پس از توافق، مالکیت انحصاری با شرکت",
        application_deadline=now + timedelta(days=45),
        contact_name="سارا کریمی", contact_channel="جلسه حضوری پس از پذیرش NDA",
        status="under_review", created_by=rep.id)
    db.add(p2)
    db.flush()
    for s in ["بینایی ماشین", "یادگیری عمیق", "Python"]:
        db.add(ProblemRequiredSkill(problem_id=p2.id, skill_id=skills[s].id, min_level=3))

    p3 = IndustrialProblem(
        owner_organization_id=parstekhno.id, title="پایش پیش‌بینانه پمپ‌های ایستگاه پمپاژ",
        summary="مدل پیش‌بینی خرابی پمپ‌ها بر مبنای داده ارتعاش و دما برای کاهش توقف ناخواسته.",
        description="سه سال داده ارتعاش و دمای پمپ‌ها موجود است. هدف ساخت مدل پایش پیش‌بینانه و داشبورد پایش.",
        category="نگهداری و تعمیرات", industry_code="MAN-01",
        expected_outcomes=["مدل پیش‌بینی خرابی", "داشبورد پایش", "راهنمای استقرار"],
        acceptance_criteria=["F1 مدل ≥ ۰٫۸", "اجرای پایلوت روی ۳ پمپ"],
        duration_days=180, budget_min=250_000_000, budget_max=400_000_000, budget_confirmed=True,
        work_mode="hybrid", confidentiality_level="public",
        ip_policy_summary="مالکیت خروجی مشترک", contact_name="رضا محمدی",
        status="converted_to_project", created_by=rep.id, created_at=now - timedelta(days=45))
    db.add(p3)
    db.flush()
    for s in ["پردازش سیگنال", "یادگیری ماشین", "IoT"]:
        db.add(ProblemRequiredSkill(problem_id=p3.id, skill_id=skills[s].id, min_level=2))

    p4 = IndustrialProblem(
        owner_organization_id=fezla.id, title="داشبورد مانیتورینگ مصرف انرژی کارخانه",
        summary="طراحی داشبورد پایش لحظه‌ای مصرف برق و گاز کارخانه فولاد.",
        description="در حال تکمیل اطلاعات؛ نیازمند تعیین دقیق دامنه و معیار پذیرش قبل از ارسال.",
        category="انرژی و بهره‌وری", industry_code="MET-02",
        expected_outcomes=["داشبورد تحت وب"], acceptance_criteria=[],
        work_mode="remote", confidentiality_level="public",
        status="draft", created_by=rep2.id)
    db.add(p4)
    db.flush()
    db.add(ProblemRequiredSkill(problem_id=p4.id, skill_id=skills["داشبوردسازی"].id, min_level=3))

    # ---------- بررسی‌ها ----------
    db.add(ProblemReview(problem_id=p1.id, reviewer_id=expert.id, decision="approve",
                         note="هدف، خروجی و معیار پذیرش روشن است؛ مناسب انتشار",
                         created_at=now - timedelta(days=9)))
    db.add(ProblemReview(problem_id=p2.id, reviewer_id=expert.id, decision="approve",
                         note="شرح فنی کافی؛ نیازمند تأیید مدیر دفتر برای انتشار",
                         created_at=now - timedelta(days=2)))

    # ---------- درخواست‌های همکاری ----------
    a1 = Application(problem_id=p1.id, applicant_user_id=st1.id, proposed_role="تحلیل‌گر داده",
                     fit_statement="مهارت تحلیل داده و Python verified دارم و پایان‌نامه‌ام در حوزه بهینه‌سازی انرژی است.",
                     related_background="پروژه تحلیل داده مصرف برق ساختمان دانشگاه",
                     weekly_hours=15, available_from="فوری", initial_plan="تحلیل داده، مدل‌سازی و پیشنهاد برنامه",
                     consent_data_share=True, status="under_review", created_at=now - timedelta(days=5))
    a2 = Application(problem_id=p1.id, applicant_user_id=st2.id, team_name="تیم داده‌کاوی نوآوران",
                     proposed_role="مهندس یادگیری ماشین", fit_statement="تجربه مدل‌سازی سری‌زمانی و داشبوردسازی داریم.",
                     weekly_hours=20, available_from="هفته آینده", consent_data_share=True,
                     status="shortlisted", decision_reason="تجربه مرتبط و تیم کامل؛ منتظر جلسه مصاحبه",
                     decided_by=rep.id, decided_at=now - timedelta(days=2), created_at=now - timedelta(days=6))
    db.add_all([a1, a2])
    db.flush()
    am = ApplicationMember(application_id=a2.id, user_id=st3.id, role="تحلیل‌گر",
                           status=TeamMemberStatus.accepted)
    db.add(am)
    db.add(Application(problem_id=p1.id, applicant_user_id=prof1.id, proposed_role="مسئول علمی",
                       fit_statement="سابقه سه طرح صنعتی در حوزه انرژی و بهینه‌سازی دارم.",
                       weekly_hours=6, available_from="۱ دی", status="submitted",
                       created_at=now - timedelta(days=3)))
    a3 = Application(problem_id=p3.id, applicant_user_id=prof2.id, proposed_role="مسئول علمی",
                     fit_statement="تیم من در پردازش سیگنال و یادگیری ماشین تجربه پایش پیش‌بینانه دارد.",
                     related_background="پروژه پایش خرابی موتورهای الکتریکی با یک کارخانه دیگر",
                     weekly_hours=8, available_from="فوری", status="accepted",
                     decision_reason="تناسب کامل تخصصی و ظرفیت اجرایی", decided_by=rep.id,
                     decided_at=now - timedelta(days=20), created_at=now - timedelta(days=25))
    db.add(a3)
    db.flush()
    db.add(ApplicationMember(application_id=a3.id, user_id=st2.id, role="مهندس مدل",
                             status=TeamMemberStatus.accepted))

    # ---------- اجرای تطبیق نمونه ----------
    from app.services.matching import run_matching
    run = run_matching(db, p1, rep.id)
    run.created_at = now - timedelta(days=4)

    # ---------- پروژه همکاری ----------
    proj = CollaborationProject(
        problem_id=p3.id, application_id=a3.id, code="COL-2026A1B2C3",
        title="همکاری صنعتی: پایش پیش‌بینانه پمپ‌های ایستگاه پمپاژ",
        scope="ساخت مدل پیش‌بینی خرابی پمپ‌ها و داشبورد پایش بر مبنای سه سال داده ارتعاش",
        acceptance_summary="؛ ".join(p3.acceptance_criteria),
        industry_org_id=parstekhno.id, university_org_id=uni.id,
        academic_lead_user_id=prof2.id, industry_rep_user_id=rep.id,
        agreement_ref="CT-2026-114", nda_ref=None,
        status="active", started_at=now - timedelta(days=12), created_by=rep.id,
        created_at=now - timedelta(days=15))
    db.add(proj)
    db.flush()
    db.add_all([
        ProjectMember(project_id=proj.id, user_id=prof2.id, organization_id=uni.id, role="مسئول علمی"),
        ProjectMember(project_id=proj.id, user_id=st2.id, organization_id=uni.id, role="مهندس مدل"),
        ProjectMember(project_id=proj.id, user_id=rep.id, organization_id=parstekhno.id, role="نماینده صنعت"),
        AgreementReference(project_id=proj.id, ref_type="contract", reference_code="CT-2026-114"),
        ProjectMilestone(project_id=proj.id, title="تحلیل داده ارتعاش", due_date="۱۴۰۵/۰۹/۳۰", status="done",
                         completed_at=now - timedelta(days=3)),
        ProjectMilestone(project_id=proj.id, title="مدل اولیه پیش‌بینی", due_date="۱۴۰۵/۱۰/۲۰", status="pending"),
        ProjectMilestone(project_id=proj.id, title="داشبورد و پایلوت", due_date="۱۴۰۵/۱۱/۲۵", status="pending"),
        Deliverable(project_id=proj.id, title="گزارش تحلیل داده ارتعاش", description="تحلیل EDA و استخراج ویژگی‌ها",
                    status=DeliverableStatus.submitted, submitted_by=prof2.id,
                    submitted_at=now - timedelta(days=1)),
    ])

    # ---------- داده بازار ----------
    s1 = MarketDataSource(name="آگهی‌های اشتغال تخصصی مجاز", source_type="job_ads",
                          url="https://jobs.example.ir", license_note="استفاده تجمیعی، بدون بازنشر رکورد",
                          coverage_note="پوشش ~۴۰٪ آگهی‌های فنی کشور؛ ماهانه به‌روزرسانی",
                          last_fetched_at=now - timedelta(days=2))
    s2 = MarketDataSource(name="نظرسنجی سالانه سازمان‌های صنعتی", source_type="survey",
                          license_note="گزارش تجمیعی", coverage_note="۶۸ شرکت عضو انجمن؛ نمونه محدود",
                          last_fetched_at=now - timedelta(days=20))
    db.add_all([s1, s2])
    db.flush()
    months = [(now - timedelta(days=30 * i)).strftime("%Y-%m") for i in range(5, -1, -1)]
    base = {"تحلیل داده": (120, 3), "یادگیری ماشین": (90, 2.2), "Python": (150, 2),
            "بینایی ماشین": (35, 1.6), "IoT": (50, 1.4), "پردازش سیگنال": (28, 1.3),
            "داشبوردسازی": (60, 1.15), "مهندسی صنایع": (75, 1.05)}
    for sname, (b, growth) in base.items():
        for i, m in enumerate(months):
            cnt = int(b * (1 + (growth - 1) * i / 5))
            db.add(MarketObservation(source_id=s1.id, skill_raw=sname, skill_id=skills[sname].id,
                                     industry_code="MAN-01", region="تهران", demand_count=cnt,
                                     observed_month=m))
            if i >= 3:
                db.add(MarketObservation(source_id=s2.id, skill_raw=sname, skill_id=skills[sname].id,
                                         industry_code=None, region="کشور", demand_count=max(3, cnt // 10),
                                         observed_month=m))
    db.add(IntegrationRun(system_name="market-data-job", direction="import", status="ok",
                          records=len(months) * len(base), note="دریافت دوره‌ای آگهی‌ها — اجرای شبانه",
                          ran_at=now - timedelta(days=2)))

    # ---------- تجاری‌سازی ----------
    case = CommercializationCase(
        title="بسته نرم‌افزاری پایش پیش‌بینانه برای صنایع فرآیندی",
        rationale=("مدل پروژه COL-2026A1B2C3 با F1 بالا روی داده واقعی اجرا شد؛ سه کارخانه دیگر نیز "
                   "در نظرسنجی به این نیاز اشاره کرده‌اند. ادعای بازار از گزارش نظرسنجی استخراج شده است."),
        application_fields=["نگهداری و تعمیرات صنایع فرآیندی", "پایش پمپ و کمپرسور"],
        evidence=[{"claim": "دقت مدل F1=0.83 روی داده پایلوت", "source": "گزارش پایلوت پروژه COL-2026A1B2C3", "kind": "explicit"},
                  {"claim": "نیاز بازار در صنایع فرآیندی", "source": "نظرسنجی سالانه سازمان‌های صنعتی", "kind": "explicit"},
                  {"claim": "امکان فروش به‌صورت SaaS", "source": "استنباط از روند آگهی‌های IoT", "kind": "inference"}],
        uncertainties="هزینه استقرار در کارخانه‌های کوچک نامشخص است؛ وضعیت مالکیت فکری خروجی نیازمند استعلام حقوقی.",
        market_signal="رشد ~۴۰٪ آگهی‌های مرتبط با IoT در شش ماه گذشته (منبع: آگهی‌های اشتغال مجاز)",
        created_by=cio.id, status=CommCaseStatus.suggested)
    db.add(case)

    # ---------- اعلان‌ها ----------
    db.add_all([
        Notification(user_id=cio.id, title="مسئله جدید در صف بررسی",
                     body="«سیستم بینایی ماشین بازرسی کیفیت قطعات» منتظر تصمیم انتشار است.",
                     link="/problems", created_at=now - timedelta(days=2)),
        Notification(user_id=cio.id, title="سازمان در انتظار احراز",
                     body="«فلزآوران اصفهان» مدارک اولیه را ثبت کرده است.", link="/review/organizations",
                     created_at=now - timedelta(days=1)),
        Notification(user_id=st1.id, title="درخواست شما در بررسی است",
                     body="درخواست همکاری شما برای «بهینه‌سازی مصرف انرژی» توسط دفتر در جریان بررسی است.",
                     link="/applications", created_at=now - timedelta(days=2)),
    ])
    db.commit()
    print("Seed done:")
    print(f"  users={db.query(User).count()} orgs={db.query(Organization).count()} "
          f"problems={db.query(IndustrialProblem).count()} apps={db.query(Application).count()} "
          f"projects={db.query(CollaborationProject).count()} "
          f"match_results={db.query(MatchResult).count()}")


if __name__ == "__main__":
    main(reset="--reset" in sys.argv)
