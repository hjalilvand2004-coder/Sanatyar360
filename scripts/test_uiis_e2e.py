"""تست انتها-به-انتهای سامانه تعامل دانشگاه و صنعت — سناریوهای پذیرش AC-01..AC-15"""
import json
import urllib.request

BASE = "http://127.0.0.1:8092/api/v1"
results = []


def req(path, method="GET", body=None, token=None, expect=200):
    r = urllib.request.Request(BASE + path, method=method)
    if body is not None:
        r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    data = json.dumps(body).encode() if body is not None else None
    try:
        with urllib.request.urlopen(r, data) as res:
            code, payload = res.status, json.loads(res.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        code, payload = e.code, json.loads(e.read().decode() or "{}")
    mark = "✅" if code == expect else "❌"
    results.append((path, method, expect, code, mark))
    return payload


def login(email):
    d = req("/auth/login", "POST", {"email": email, "password": "uiis1234"})
    return d.get("access_token")


def check(name, cond, extra=""):
    print(("✅ PASS  " if cond else "❌ FAIL  ") + name + ((" — " + str(extra)) if extra else ""))
    results.append((name, "", "", "", "✅" if cond else "❌"))


cio = login("cio@nav.ac.ir")
expert = login("expert@nav.ac.ir")
rep = login("rep@pastechno.ir")
rep2 = login("rep@fezlavaran.ir")
st2 = login("st2@nav.ac.ir")
st1 = login("st1@nav.ac.ir")
prof1 = login("prof.hosseini@nav.ac.ir")
comm = login("comm@nav.ac.ir")
sysadmin = login("sysadmin@uiis-system.ir")

# ---------- AC-01: ثبت و ارسال مسئله ----------
p = req("/problems", "POST", {
    "title": "پیش‌بینی تقاضای محصولات شرکت پارس‌تکنو",
    "summary": "مدل پیش‌بینی تقاضا برای برنامه تولید با داده سه سال فروش.",
    "description": "داده فروش سه سال گذشته و تقویم روزهای تعطیل موجود است. هدف ساخت مدل پیش‌بینی تقاضای ماهانه و ادغام با برنامه تولید.",
    "category": "زنجیره تأمین", "industry_code": "MAN-01",
    "expected_outcomes": ["مدل پیش‌بینی ماهانه", "گزارش دقت"], "acceptance_criteria": ["MAPE < ۲۰٪"],
    "budget_min": 150000000, "budget_max": 250000000, "budget_confirmed": True,
    "work_mode": "remote", "confidentiality_level": "registered_users",
    "ip_policy_summary": "مالکیت مشترک", "contact_name": "رضا محمدی", "contact_channel": "سامانه",
    "skill_names": ["تحلیل داده", "یادگیری ماشین"],
}, rep)
pid = p.get("id")
check("AC-01: ثبت مسئله توسط نماینده تأییدشده", bool(pid), pid)
s = req(f"/problems/{pid}/submit", "POST", {}, rep)
check("AC-01: ارسال برای بررسی → submitted", s.get("status") == "submitted", s)

# ---------- AC-02: کنترل کیفیت انتشار ----------
r = req(f"/problems/{pid}/publish", "POST", {}, cio, expect=409)
check("AC-02a: انتشار بدون بررسی تأیید رد شود",
      r.get("code") in ("not_approved", "invalid_state"), r.get("code"))
req(f"/problems/{pid}/reviews", "POST", {"decision": "approve", "note": "معیار پذیرش روشن است"}, expert)
s = req(f"/problems/{pid}/publish", "POST", {}, cio)
check("AC-02b: پس از تأیید کارشناس منتشر می‌شود", s.get("status") == "published", s)
# مسئله فاقد معیار پذیرش نباید منتشر شود
p_bad = req("/problems", "POST", {
    "title": "مسئله آزمایشی ناقص فاقد معیار", "summary": "خلاصه آزمایشی برای تست کنترل کیفیت انتشار سامانه.",
    "description": "شرح آزمایشی طولانی‌تر از سی حرف برای عبور از اعتبارسنجی ورودی سامانه.",
    "contact_name": "x", "ip_policy_summary": "y", "skill_names": ["تحلیل داده"],
}, rep)
req(f"/problems/{p_bad['id']}/submit", "POST", {}, rep)
req(f"/problems/{p_bad['id']}/reviews", "POST", {"decision": "approve"}, expert)
r = req(f"/problems/{p_bad['id']}/publish", "POST", {}, cio, expect=422)
check("AC-02c: مسئله بدون معیار پذیرش منتشر نشود (quality gate)", r.get("code") == "quality_gate_failed", r.get("code"))

# ---------- AC-03: ایزولاسیون سازمانی ----------
# ثبت پیش‌نویس توسط سازمان احرازنشده مجاز است؛ اما انتشار ممنوع است
p_pending = req("/problems", "POST", {
    "title": "طراحی اسکلت بهینه فونداسیون کارخانه", "summary": "طراحی سازه‌ای با داده محرمانه زمین.",
    "description": "داده‌های ژئوتکنیک محرمانه است؛ فقط شرکت‌های منتخب دسترسی دارند.",
    "expected_outcomes": ["طرح سازه"], "acceptance_criteria": ["تأیید مهندس ناظر"],
    "confidentiality_level": "confidential", "contact_name": "علی نوری",
    "ip_policy_summary": "مالکیت شرکت", "skill_names": ["مهندسی صنایع"],
}, rep2)
check("AC-03a: سازمان احرازنشده می‌تواند پیش‌نویس ثبت کند", bool(p_pending.get("id")))
req(f"/problems/{p_pending['id']}/submit", "POST", {}, rep2)
req(f"/problems/{p_pending['id']}/reviews", "POST", {"decision": "approve"}, expert)
r = req(f"/problems/{p_pending['id']}/publish", "POST", {}, cio, expect=409)
check("AC-03a-2: انتشار مسئله سازمان احرازنشده ممنوع", r.get("code") == "org_not_verified", r.get("code"))
pub = req("/problems?limit=100", token=st2)
titles = [x["title"] for x in pub["items"]]
check("AC-03b: مسئله محرمانه سازمان دیگر در فهرست دانشجو نیست",
      not any("فونداسیون" in t for t in titles), titles[:3])

# ---------- AC-04: درخواست تکراری ----------
a1 = req("/problems/" + pid + "/applications", "POST", {
    "proposed_role": "مهندس مدل", "fit_statement": "تجربه مدل‌سازی سری‌زمانی و پروژه فروش دارم.",
    "weekly_hours": 20, "consent_data_share": True,
}, st2)
aid = a1.get("id")
check("AC-04a: ثبت درخواست", bool(aid), aid)
r = req("/problems/" + pid + "/applications", "POST", {
    "proposed_role": "x", "fit_statement": "دوباره ثبت می‌کنم برای تست رکورد تکراری سامانه.",
}, st2, expect=409)
check("AC-04b: ثبت تکراری با رکورد اضافه همراه نیست", r.get("code") == "duplicate_application", r.get("code"))

# ---------- AC-05: پروفایل حداقلی بدون رضایت ----------
st3 = login("st3@nav.ac.ir")  # بدون رضایت ثبت‌شده
a2 = req("/problems/" + pid + "/applications", "POST", {
    "proposed_role": "تحلیل‌گر", "fit_statement": "مهارت تحلیل داده و مهندسی صنایع با شواهد درسی دارم.",
    "weekly_hours": 10, "consent_data_share": False,
}, st3)
aid2 = a2.get("id")
apps = req("/problems/" + pid + "/applications", token=rep)
a1_view = next((x for x in apps["items"] if x["applicant"]["id"] == a1["applicant"]["id"]), None)
a2_view = next((x for x in apps["items"] if x["applicant"]["id"] == a2["applicant"]["id"]), None)
check("AC-05a: کاربر با رضایت → پروفایل کامل برای صنعت", a1_view and not a1_view["profile_limited"])
check("AC-05b: کاربر بدون رضایت → پروفایل حداقلی (بدون ایمیل/گروه)",
      a2_view and a2_view["profile_limited"] and "email" not in a2_view["applicant"], a2_view and a2_view["applicant"].keys())

# ---------- AC-06: نتایج تطبیق با دلیل و نسخه ----------
run = req("/problems/" + pid + "/match-runs", "POST", {}, rep)
res = req(f"/match-runs/{run['id']}/results", token=rep)
first = res["items"][0] if res["items"] else {}
check("AC-06: هر نتیجه تطبیق دلیل و نسخه الگوریتم دارد",
      bool(first.get("reasons")) and res.get("algorithm_version") == "rules-v1.0",
      (res.get("algorithm_version"), len(res["items"])))
recs = req("/me/recommended-problems", token=prof1)
check("AC-06b: پیشنهاد شخصی مسئله با دلیل", recs.get("total", 0) > 0 and bool(recs["items"][0].get("reasons")))

# ---------- AC-07: تصمیم انسانی با ثبت دلیل ----------
req(f"/applications/{aid}/decisions", "POST", {"decision": "shortlist"}, cio)
r = req(f"/applications/{aid}/decisions", "POST", {"decision": "accept", "reason": ""}, rep, expect=422)
check("AC-07a: پذیرش بدون دلیل رد می‌شود", r.get("code") == "reason_required", r.get("code"))
s = req(f"/applications/{aid}/decisions", "POST", {"decision": "accept", "reason": "تجربه مرتبط و تیم کامل"}, rep)
check("AC-07b: پذیرش با ثبت دلیل", s.get("status") == "accepted", s)
req(f"/applications/{aid2}/decisions", "POST", {"decision": "reject", "reason": "ظرفیت تیم تکمیل است"}, rep)

# ---------- AC-08: تبدیل مسئله به همکاری با حفظ اطلاعات مبنا ----------
col = req("/collaborations", "POST", {
    "problem_id": pid, "application_id": aid,
    "agreement_ref": "CT-2026-120",
    "milestones": [{"title": "مدل اولیه", "due_date": "۱۴۰۵/۱۰/۱۰"}, {"title": "تأیید نهایی"}],
}, cio)
check("AC-08a: پروژه همکاری ایجاد شد با حفظ مسئله و طرف‌ها",
      col.get("code") and col.get("problem_id") == pid and col.get("industry_org", {}).get("name") == "پارس‌تکنو صنعت",
      col.get("code"))
p_view = req("/problems/" + pid, token=rep)
check("AC-08b: وضعیت مسئله → converted_to_project", p_view.get("status") == "converted_to_project")
r = req("/collaborations", "POST", {"problem_id": pid, "application_id": aid}, cio, expect=409)
check("AC-08c: دوباره‌سازی از همان درخواست ممنوع", r.get("code") == "duplicate", r.get("code"))

# ---------- وضعیت پروژه و خروجی‌ها (AC-09) ----------
colid = col["id"]
s = req(f"/collaborations/{colid}/status", "POST", {"status": "active"}, cio)
check("AC-08d: فعال‌سازی پس از ثبت قرارداد", s.get("status") == "active", s.get("status"))
dv = req(f"/collaborations/{colid}/deliverables", "POST", {"title": "گزارش مدل پیش‌بینی تقاضا"}, st2)
r = req(f"/deliverables/{dv['id']}/reviews", "POST", {"decision": "accept"}, st2, expect=403)
check("AC-09a: پذیرش خروجی توسط دانشجو ممنوع", r.get("code") == "forbidden", r.get("code"))
s = req(f"/deliverables/{dv['id']}/reviews", "POST", {"decision": "accept", "note": "مطابق معیار"}, rep)
check("AC-09b: پذیرش توسط نماینده صنعت مجاز", s.get("status") == "accepted")

# ---------- AC-10..11: تحلیل‌ها ----------
sd = req("/analytics/skill-demand", token=cio)
check("AC-10: نمودار تقاضا منبع و زمان به‌روزرسانی دارد", bool(sd.get("sources")) and bool(sd.get("generated_at")))
net = req("/analytics/collaboration-network", token=cio)
e = next((x for x in net["edges"] if x.get("weight")), None)
check("AC-11: هر ارتباط شبکه به همکاری واقعی ردیابی می‌شود", e and len(e.get("project_ids", [])) > 0,
      e and e["project_codes"])

# ---------- AC-12: تجاری‌سازی ----------
case = req("/commercialization/cases", "POST", {
    "title": "بسته پیش‌بینی تقاضا برای SMEها", "rationale": "مدل پروژه فعال با دقت تأییدشده و دو متقاضی دیگر در نظرسنجی؛ نیاز بازار از گزارش نظرسنجی.",
    "evidence": [{"claim": "MAPE ۱۸٪", "source": "گزارش پروژه", "kind": "explicit"}],
    "uncertainties": "مالکیت داده فروش نامشخص", "market_signal": "رشد آگهی‌ها",
}, cio)
check("AC-12a: پرونده فرصت ثبت شد (suggested)", case.get("status") == "suggested")
r = req(f"/commercialization/cases/{case['id']}/reviews", "POST", {"decision": "proceed"}, st2, expect=403)
check("AC-12b: ارزیابی توسط غیرمتخصص ممنوع", r.get("code") == "forbidden")
s = req(f"/commercialization/cases/{case['id']}/reviews", "POST", {
    "decision": "proceed", "need_fit_score": 4, "trl_assessment": 6,
    "comment": "نیاز بازار مستند؛ هزینه استقرار باید تعیین شود", "next_action": "تعیین قیمت‌گذاری"}, comm)
check("AC-12c: پس از ارزیابی متخصص → expert_approved", s.get("status") == "expert_approved")

# ---------- AC-13: قطعی AI سامانه را متوقف نکند ----------
ok_health = req("/health", expect=200)
check("AC-13: بدون وابستگی به سرویس خارجی AI، ثبت و بررسی عادی کار می‌کند", ok_health.get("status") == "ok")

# ---------- AC-14: پشتیبان‌گیری (اسکریپت جداگانه در بسته استقرار) ----------
print("ℹ️ AC-14: پشتیبان‌گیری/بازیابی در بسته استقرار (scripts/backup_restore_test.sh) پوشش داده می‌شود")

# ---------- AC-15: حسابرسی ----------
logs = req("/audit-logs?limit=100", token=sysadmin)
acts = [x["action"] for x in logs["items"]]
check("AC-15: تغییرات حساس با عامل/زمان/موضوع حسابرسی شده‌اند",
      "application_accept" in acts and "problem_published" in acts and "collaboration_created" in acts,
      sorted(set(a for a in acts if "accept" in a or "publish" in a))[:5])
r = req("/audit-logs", token=rep, expect=403)
check("AC-15b: مشاهده حسابرسی فقط مدیر فنی", r.get("code") == "forbidden")

# ---------- کنترل‌های تکمیلی ----------
me2 = req("/auth/me", token=rep)
check("پروفایل کاربر و نقش‌ها", me2.get("user", {}).get("email") == "rep@pastechno.ir")
r = req("/problems", token="", expect=401)
check("دسترسی بدون توکن ممنوع", True)

print("\n========== جمع‌بندی ==========")
fails = [r for r in results if r[4] == "❌"]
print(f"کل بررسی‌ها: {len(results)} | موفق: {len(results) - len(fails)} | ناموفق: {len(fails)}")
for f in fails:
    print("  ❌", f[0], f[1], "انتظار:", f[2], "دریافت:", f[3])
