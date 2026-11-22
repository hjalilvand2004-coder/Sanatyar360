// جزئیات مسئله: تب‌های اطلاعات، پرسش‌وپاسخ، بررسی‌ها، متقاضیان، نتایج تطبیق + اقدامات نقش‌محور
import React, { useEffect, useState } from "react";
import { api, jalali, statusBadge, money, label, fa } from "../api";
import { Card, Empty, Alert, Modal, Flow, Field } from "../ui";
import { useApp } from "../App";

export default function ProblemDetail({ route }: any) {
  const id = route.slice("/problem/".length);
  const { me, nav, notify, userType, myRoles } = useApp();
  const [p, setP] = useState<any>(null);
  const [tab, setTab] = useState("info");
  const [err, setErr] = useState("");
  const [qa, setQa] = useState<any[]>([]);
  const [reviews, setReviews] = useState<any[]>([]);
  const [apps, setApps] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [results, setResults] = useState<any[]>([]);
  const [activeRun, setActiveRun] = useState<string>("");
  const [gap, setGap] = useState<any>(null);
  const [modal, setModal] = useState<"" | "apply" | "review" | "answer" | "question">("");
  const [editingQ, setEditingQ] = useState<string>("");

  const isIndustry = me.memberships.some((m: any) =>
    p && m.organization_id === p.owner.id && ["industry_rep", "industry_manager"].includes(m.role));
  const isCio = [...myRoles].some((r: string) => ["cio_manager", "cio_expert"].includes(r));
  const isAcademic = userType === "student" || userType === "professor";

  const load = () => {
    api("/problems/" + id).then((d) => setP(d)).catch((e: any) => { setErr(e.message); setP(null); });
    api("/problems/" + id + "/reviews").then((d) => setReviews(d.items)).catch(() => {});
    if (isCio || isIndustry) {
      api("/problems/" + id + "/applications").then((d) => setApps(d.items)).catch(() => {});
    }
    if (isAcademic) {
      api("/maharat/skill-gap/" + id).then(setGap).catch(() => setGap(null));
    }
  };
  useEffect(load, [id]);

  if (err) return <Alert kind="error">{err}</Alert>;
  if (!p) return <Empty text="در حال بارگذاری…" />;
  if (p.restricted_access) {
    return (
      <div>
        <Alert kind="warn">
          این مسئله با سطح دسترسی «{label(p.confidentiality_level)}» ثبت شده و جزئیات کامل آن برای نقش شما قابل نمایش نیست.
          فقط خلاصه عمومی نشان داده می‌شود. برای دسترسی، پذیرش NDA و مجوز سازمان مالک لازم است.
        </Alert>
        <Card title={p.title}>
          <div className="detail-grid">
            <dt>سازمان</dt><dd>{p.owner.name}</dd>
            <dt>خلاصه عمومی</dt><dd>{p.summary}</dd>
            <dt>حوزه</dt><dd>{p.category || "—"} ({p.industry_code || "—"})</dd>
            <dt>مهارت‌های موردنیاز</dt><dd>{p.required_skills.join(" • ") || "—"}</dd>
          </div>
        </Card>
      </div>
    );
  }

  const publish = async () => {
    try { await api("/problems/" + id + "/publish", { method: "POST" }); notify("مسئله منتشر شد"); load(); }
    catch (e: any) { setErr(e.message); }
  };
  const submit = async () => {
    try { await api("/problems/" + id + "/submit", { method: "POST" }); notify("برای بررسی ارسال شد"); load(); }
    catch (e: any) { setErr(e.message); }
  };
  const closeCall = async () => {
    try { await api("/problems/" + id + "/close", { method: "POST", body: { reason: "پایان مهلت/بستن توسط صنعت" } }); notify("فراخوان بسته شد"); load(); }
    catch (e: any) { setErr(e.message); }
  };
  const runMatch = async () => {
    try {
      const d = await api("/problems/" + id + "/match-runs", { method: "POST" });
      setActiveRun(d.id); setTab("matches");
      const r = await api("/match-runs/" + d.id + "/results");
      setResults(r.items); notify(`تطبیق اجرا شد — ${fa(r.total)} نامزد`);
    } catch (e: any) { setErr(e.message); }
  };

  const flowStates = ["پیش‌نویس", "ارسال", "بررسی", "انتشار", "همکاری"];
  const flowMap: Record<string, string> = {
    draft: "پیش‌نویس", submitted: "ارسال", under_review: "بررسی", needs_revision: "بررسی",
    published: "انتشار", applications_closed: "انتشار", converted_to_project: "همکاری",
  };

  return (
    <div>
      {err && <Alert kind="error">{err}</Alert>}
      <Card title={p.title} extra={statusBadge(p.status)}>
        <Flow states={flowStates} current={flowMap[p.status]} />
        <dl className="detail-grid" style={{ marginTop: 14 }}>
          <dt>سازمان مالک</dt><dd>{p.owner.name} {statusBadge(p.owner.status)}</dd>
          <dt>حوزه / کد صنعت</dt><dd>{p.category || "—"} / {p.industry_code || "—"}</dd>
          <dt>نوع اجرا</dt><dd>{label(p.work_mode)} {p.location ? "— " + p.location : ""}</dd>
          <dt>مدت تخمینی</dt><dd>{p.duration_days ? fa(p.duration_days) + " روز" : "—"}</dd>
          <dt>بودجه</dt><dd>{money(p.budget_min, p.currency) || "—"} {p.budget_max ? " تا " + money(p.budget_max, p.currency) : ""} {p.budget_confirmed ? "✅ قطعی" : "(غیرقطعی)"}</dd>
          <dt>مهلت درخواست</dt><dd>{jalali(p.application_deadline)}</dd>
          <dt>سطح محرمانگی</dt><dd>{statusBadge(p.confidentiality_level)} {p.nda_required ? "| نیازمند NDA" : ""}</dd>
          <dt>مالکیت فکری</dt><dd>{p.ip_policy_summary || "—"}</dd>
          <dt>مسئول پاسخ‌گویی</dt><dd>{p.contact_name || "—"} — {p.contact_channel || "—"}</dd>
          <dt>منابع قابل ارائه</dt><dd>{p.resources_offered || "—"}</dd>
          <dt>نسخه</dt><dd>v{fa(p.version)} — آخرین به‌روزرسانی {jalali(p.updated_at, true)}</dd>
        </dl>
        <div className="chips" style={{ marginTop: 10 }}>
          {p.required_skills_full?.map((s: any) => <span key={s.skill} className="chip">{s.skill} (حداقل سطح {fa(s.min_level)})</span>)}
        </div>
        <div className="btn-row" style={{ marginTop: 16 }}>
          {isIndustry && ["draft", "needs_revision"].includes(p.status) && <>
            <button className="btn primary" onClick={submit}>ارسال برای بررسی</button>
            <button className="btn" onClick={() => nav("/problems/new?edit=" + id)}>ویرایش نسخه جدید</button>
          </>}
          {isIndustry && p.status === "published" && <button className="btn warn" onClick={closeCall}>بستن فراخوان</button>}
          {isCio && p.status === "under_review" && <>
            <button className="btn" onClick={() => setModal("review")}>ثبت بررسی</button>
            <button className="btn ok" onClick={publish}>انتشار مسئله</button>
          </>}
          {(isIndustry || isCio) && <button className="btn" onClick={runMatch}>اجرای موتور تطبیق</button>}
          {isAcademic && p.status === "published" && !p.my_application && (
            <button className="btn primary" onClick={() => setModal("apply")}>ثبت درخواست همکاری</button>
          )}
          {isAcademic && p.status === "published" && (
            <button className="btn" onClick={async () => { const d = await api("/problems/" + id + "/interests", { method: "POST" }); notify(d.interested ? "به علاقه‌مندی‌ها اضافه شد" : "از علاقه‌مندی‌ها حذف شد"); load(); }}>
              {p.my_interest ? "★ حذف علاقه‌مندی" : "☆ علاقه‌مندی"} ({fa(p.interests_count)})
            </button>
          )}
          {isAcademic && p.my_application && <button className="btn" onClick={() => nav("/applications")}>مشاهده درخواست من</button>}
        </div>
      </Card>

      {isAcademic && gap && (
        <Card title="تحلیل شکاف مهارتی با مهارت‌یار۳۶۰">
          {gap.linked === false ? (
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <p style={{ opacity: 0.8, margin: 0 }}>سطح تأییدشده مهارت‌های شما (از مدارک و پروژه‌های مهارت‌یار۳۶۰) برای این مسئله موجود نیست.</p>
              <button className="btn" onClick={() => nav("/maharat")}>پیوند پروفایل مهارت‌یار</button>
            </div>
          ) : (
            <>
              <div className="chips" style={{ marginBottom: 8 }}>
                <span className="chip">پوشش مهارت‌های الزامی: {fa(Math.round((gap.coverage || 0) * 100))}٪</span>
                {gap.is_sample && <span className="chip">داده نمونه اکوسیستم</span>}
              </div>
              <div className="tbl-wrap"><table className="tbl">
                <thead><tr><th>مهارت مسئله</th><th>معادل در مهارت‌یار</th><th>سطح شما</th><th>حداقل لازم</th><th>شواهد</th><th>وضعیت</th></tr></thead>
                <tbody>
                  {gap.items.map((x: any, i: number) => (
                    <tr key={i}>
                      <td>{x.skill}</td>
                      <td>{x.maharat_skill || "—"}</td>
                      <td>{x.maharat_level != null ? fa(Math.round(x.maharat_level)) + "/۱۰۰" : "—"}</td>
                      <td>{fa(x.required_level)}</td>
                      <td title={x.top_evidence || ""}>{x.evidence_count ? fa(x.evidence_count) + " مدرک" : "—"}</td>
                      <td>{x.verdict}</td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
              <p style={{ fontSize: 12, opacity: 0.6, marginTop: 6 }}>{gap.note}</p>
            </>
          )}
        </Card>
      )}

      <div className="tabbar">
        {[["info", "شرح مسئله"], ["qa", "پرسش و پاسخ"], ["reviews", "بررسی‌ها"],
          ...(isIndustry || isCio ? [["apps", `متقاضیان (${fa(apps.length)})`], ["matches", "نتایج تطبیق"], ["team", "تیم پیشنهادی"]] : [])]
          .map(([k, t]) => <button key={k as string} className={tab === k ? "active" : ""} onClick={() => setTab(k as string)}>{t}</button>)}
      </div>

      {tab === "info" && (
        <Card title="شرح کامل">
          <p style={{ whiteSpace: "pre-wrap" }}>{p.description}</p>
          <hr className="divider" />
          <div className="grid cols-2">
            <div><h3>خروجی‌های مورد انتظار</h3><ul>{p.expected_outcomes?.map((o: string, i: number) => <li key={i}>{o}</li>)}</ul></div>
            <div><h3>معیارهای پذیرش</h3><ul>{p.acceptance_criteria?.map((o: string, i: number) => <li key={i}>{o}</li>)}</ul></div>
          </div>
        </Card>
      )}

      {tab === "qa" && <QaTab problemId={id} qa={qa} setQa={setQa} canAnswer={isIndustry || isCio} setEditingQ={setEditingQ} editingQ={editingQ} modal={modal} setModal={setModal} load={load} />}

      {tab === "reviews" && (
        <Card title="سوابق بررسی کارشناسان">
          {reviews.length === 0 ? <Empty /> : reviews.map((r) => (
            <div key={r.id} style={{ borderBottom: "1px solid var(--border)", paddingBottom: 10, marginBottom: 10 }}>
              <b>{r.reviewer.full_name}</b> {statusBadge(r.decision)} <span className="muted">{jalali(r.created_at, true)}</span>
              {r.note && <p style={{ margin: "6px 0 0" }}>{r.note}</p>}
            </div>
          ))}
          {isCio && p.status === "under_review" && <button className="btn" onClick={() => setModal("review")}>ثبت بررسی جدید</button>}
        </Card>
      )}

      {tab === "apps" && (
        <Card title="متقاضیان مجاز">
          {apps.length === 0 ? <Empty text="متقاضی‌ای ثبت نشده است" /> : (
            <div className="tbl-wrap"><table className="tbl">
              <thead><tr><th>متقاضی / تیم</th><th>نقش پیشنهادی</th><th>وضعیت</th><th>ظرفیت زمانی</th><th>اطلاعات</th><th></th></tr></thead>
              <tbody>
                {apps.map((a) => (
                  <tr key={a.id}>
                    <td><b>{a.team_name || a.applicant.full_name}</b>
                      {a.profile_limited && <span className="badge gray" title="بدون رضایت اشتراک، اطلاعات حداقلی نمایش داده می‌شود">پروفایل حداقلی</span>}
                      <div className="muted">{a.fit_statement.slice(0, 90)}…</div></td>
                  <td>{a.proposed_role || "—"}</td>
                    <td>{statusBadge(a.status)}</td>
                    <td>{fa(a.weekly_hours)} ساعت/هفته</td>
                    <td>{a.profile_limited ? "بدون رضایت اشتراک" : "کامل (رضایت داده شده)"}</td>
                    <td><button className="btn sm" onClick={() => nav("/application/" + a.id)}>بررسی</button></td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
        </Card>
      )}

      {tab === "matches" && (
        <Card title="نتایج موتور تطبیق (قواعدی نسخه ۱)">
          <Alert kind="info">
            امتیاز فقط رتبه‌بندی کمکی است و «پیشنهاد سامانه» محسوب می‌شود؛ انتخاب نهایی انسانی و با ثبت دلیل انجام می‌شود (AC-07).
          </Alert>
          {results.length === 0 ? <Empty text="هنوز تطبیقی اجرا نشده — دکمه «اجرای موتور تطبیق» را بزنید" /> : (
            <div className="tbl-wrap"><table className="tbl">
              <thead><tr><th>رتبه</th><th>امتیاز</th><th>نامزد (پروفایل حداقلی)</th><th>دلایل پیشنهاد</th><th>کمبودها</th></tr></thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.rank}>
                    <td>{fa(r.rank)}</td>
                    <td><div className="match-score">{fa(Math.round(r.score * 100))}<span style={{ fontSize: 9 }}>%</span></div></td>
                    <td><b>{r.user.full_name}</b><div className="muted">{label(r.user.user_type)}</div></td>
                    <td><ul style={{ margin: 0, paddingRight: 16 }}>{r.reasons.map((x: string, i: number) => <li key={i}>{x}</li>)}</ul></td>
                    <td>{r.missing.length ? r.missing.join("، ") : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
        </Card>
      )}

      {tab === "team" && <TeamTab problemId={id} canManage={isIndustry || isCio} nav={nav} notify={notify} />}

      {modal === "apply" && <ApplyModal problem={p} onClose={() => setModal("")} onDone={() => { setModal(""); load(); nav("/applications"); }} />}
      {modal === "review" && <ReviewModal problemId={id} onClose={() => setModal("")} onDone={() => { setModal(""); load(); }} />}
      {modal === "question" && <QuestionModal problemId={id} onClose={() => setModal("")} onDone={() => { setModal(""); setTab("qa"); loadQa(id, setQa); }} />}
      {modal === "answer" && editingQ && <AnswerModal problemId={id} q={editingQ} onClose={() => setModal("")} onDone={() => { setModal(""); loadQa(id, setQa); }} />}
    </div>
  );
}

function loadQa(id: string, setQa: any) {
  api("/problems/" + id + "/questions").then((d) => setQa(d.items)).catch(() => {});
}

function QaTab({ problemId, qa, setQa, canAnswer, setEditingQ, editingQ, modal, setModal }: any) {
  useEffect(() => { loadQa(problemId, setQa); }, [problemId]);
  return (
    <Card title="پرسش و پاسخ کنترل‌شده" extra={
      <button className="btn sm primary" onClick={() => setModal("question")}>پرسش جدید</button>}>
      {qa.length === 0 ? <Empty text="پرسشی ثبت نشده است" /> : qa.map((x) => (
        <div key={x.id} style={{ borderBottom: "1px solid var(--border)", paddingBottom: 10, marginBottom: 10 }}>
          <b>{x.user.full_name}:</b> {x.question}
          {x.answer ? <div style={{ background: "rgba(52,211,153,0.12)", borderRadius: 8, padding: "8px 12px", marginTop: 6 }}>پاسخ: {x.answer}</div>
            : canAnswer && <button className="btn sm" onClick={() => { setEditingQ(x.id); setModal("answer"); }}>پاسخ</button>}
        </div>
      ))}
    </Card>
  );
}

function QuestionModal({ problemId, onClose, onDone }: any) {
  const [text, setText] = useState("");
  return (
    <Modal title="پرسش از سازمان" onClose={onClose}>
      <Field label="متن پرسش"><textarea value={text} onChange={(e: any) => setText(e.target.value)} /></Field>
      <button className="btn primary" disabled={text.length < 5} onClick={async () => { await api("/problems/" + problemId + "/questions", { method: "POST", body: { question: text } }); onDone(); }}>ارسال پرسش</button>
    </Modal>
  );
}

function AnswerModal({ problemId, q, onClose, onDone }: any) {
  const [text, setText] = useState("");
  return (
    <Modal title="پاسخ به پرسش" onClose={onClose}>
      <Field label="پاسخ"><textarea value={text} onChange={(e: any) => setText(e.target.value)} /></Field>
      <button className="btn primary" onClick={async () => { await api(`/problems/${problemId}/questions/${q}/answer`, { method: "POST", body: { answer: text } }); onDone(); }}>ثبت پاسخ</button>
    </Modal>
  );
}

function ApplyModal({ problem, onClose, onDone }: any) {
  const [form, setForm] = useState({ proposed_role: "", team_name: "", fit_statement: "", related_background: "", weekly_hours: 10, available_from: "", initial_plan: "", consent_data_share: true });
  const [err, setErr] = useState("");
  const set = (k: string, v: any) => setForm({ ...form, [k]: v });
  const submit = async () => {
    setErr("");
    try {
      await api("/problems/" + problem.id + "/applications", { method: "POST", body: form });
      onDone();
    } catch (e: any) { setErr(e.message); }
  };
  return (
    <Modal title={"ثبت درخواست همکاری — " + problem.title} onClose={onClose}>
      {err && <Alert kind="error">{err}</Alert>}
      <div className="grid cols-2">
        <Field label="نقش پیشنهادی"><input value={form.proposed_role} onChange={(e: any) => set("proposed_role", e.target.value)} placeholder="مثلاً تحلیل‌گر داده" /></Field>
        <Field label="نام تیم (اختیاری)"><input value={form.team_name} onChange={(e: any) => set("team_name", e.target.value)} /></Field>
      </div>
      <Field label="توضیح تناسب" hint="چرا این مسئله با مهارت‌ها و سابقه شما هم‌خوان است؟">
        <textarea value={form.fit_statement} onChange={(e: any) => set("fit_statement", e.target.value)} /></Field>
      <Field label="سوابق مرتبط"><textarea value={form.related_background} onChange={(e: any) => set("related_background", e.target.value)} /></Field>
      <div className="grid cols-3">
        <Field label="ظرفیت زمانی (ساعت/هفته)"><input type="number" value={form.weekly_hours} onChange={(e: any) => set("weekly_hours", +e.target.value)} /></Field>
        <Field label="آمادگی شروع"><input value={form.available_from} onChange={(e: any) => set("available_from", e.target.value)} placeholder="مثلاً هفته آینده" /></Field>
        <Field label="رضایت اشتراک اطلاعات">
          <select value={form.consent_data_share ? "1" : "0"} onChange={(e: any) => set("consent_data_share", e.target.value === "1")}>
            <option value="1">رضایت می‌دهم</option><option value="0">بدون رضایت (پروفایل حداقلی)</option>
          </select></Field>
      </div>
      <Field label="طرح اولیه حل مسئله"><textarea value={form.initial_plan} onChange={(e: any) => set("initial_plan", e.target.value)} /></Field>
      <button className="btn primary" disabled={form.fit_statement.length < 20} onClick={submit}>ثبت درخواست</button>
    </Modal>
  );
}

function ReviewModal({ problemId, onClose, onDone }: any) {
  const [decision, setDecision] = useState("approve");
  const [note, setNote] = useState("");
  const [err, setErr] = useState("");
  const go = async () => {
    setErr("");
    try { await api("/problems/" + problemId + "/reviews", { method: "POST", body: { decision, note } }); onDone(); }
    catch (e: any) { setErr(e.message); }
  };
  return (
    <Modal title="ثبت بررسی کارشناسی" onClose={onClose}>
      {err && <Alert kind="error">{err}</Alert>}
      <Field label="تصمیم">
        <select value={decision} onChange={(e: any) => setDecision(e.target.value)}>
          <option value="approve">تأیید (مسئولیت انتشار)</option>
          <option value="needs_revision">نیازمند اصلاح</option>
          <option value="reject">رد</option>
        </select></Field>
      <Field label="نظر تخصصی" hint="برای اصلاح/رد، ثبت دلیل الزامی است"><textarea value={note} onChange={(e: any) => setNote(e.target.value)} /></Field>
      <button className="btn primary" onClick={go}>ثبت بررسی</button>
    </Modal>
  );
}

// ---------- تیم‌سازی توضیح‌پذیر (v1.1.0) ----------
function TeamTab({ problemId, canManage, nav, notify }: any) {
  const [items, setItems] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const load = () => api(`/problems/${problemId}/team-proposals`).then((d: any) => setItems(d.items || [])).catch(() => {});
  useEffect(load, [problemId]);

  const build = async () => {
    setBusy(true); setErr("");
    try {
      await api(`/problems/${problemId}/team-proposals`, { method: "POST" });
      notify("پیشنهاد تیم ساخته شد"); load();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  const accept = async (pid: string) => {
    setBusy(true); setErr("");
    try {
      const d = await api(`/team-proposals/${pid}/accept`, { method: "POST" });
      notify("همکاری ساخته شد — گام بعدی: پایلوت یا قرارداد");
      nav("/collaboration/" + d.project_id);
    } catch (e: any) { setErr(e.message); setBusy(false); }
  };

  return (
    <div>
      {err && <Alert kind="error">{err}</Alert>}
      <Card title="🧩 تیم‌سازی توضیح‌پذیر — «تیم آماده حل مسئله»">
        <Alert kind="info">
          به‌جای معرفی فرد، ترکیب پیشنهادی تیم ارائه می‌شود: استاد راهبر + دانشجوی متخصص + دانشجوی
          مکمل + منابع. «تناسب (fit)» و «اطمینان به داده‌ها (confidence)» دو شاخص جدایند؛ کمبود داده
          به‌معنای ضعف فرد نیست. تصمیم پذیرش نهایی با انسان است.
        </Alert>
        {canManage && <button className="btn primary" disabled={busy} onClick={build}>
          {busy ? "در حال تحلیل…" : "ساخت پیشنهاد تیم ✦"}</button>}
        {items.length === 0 && <Empty text="هنوز پیشنهاد تیمی ساخته نشده است" />}
        {items.map((t) => (
          <div key={t.id} style={{ border: "1px solid var(--card-border)", borderRadius: 14, padding: 16, marginTop: 12 }}>
            <div className="btn-row" style={{ justifyContent: "space-between" }}>
              <span className="badge blue">{t.algorithm_version}</span>
              <span className={`badge ${t.status === "accepted" ? "green" : "gray"}`}>
                {t.status === "accepted" ? "پذیرفته‌شده ✓" : "پیشنهاد"}</span>
            </div>
            <p style={{ margin: "10px 0" }}>{t.explanation}</p>
            {t.composition.map((m: any, i: number) => (
              <div key={i} className="card" style={{ padding: "12px 14px", marginBottom: 10 }}>
                <div className="btn-row" style={{ justifyContent: "space-between" }}>
                  <b>{m.user.full_name} <span className="badge violet">{m.role_in_team}</span></b>
                  <span className="muted" style={{ fontSize: 12 }}>{m.user.department || "—"}</span>
                </div>
                <div className="grid cols-2" style={{ marginTop: 8 }}>
                  <div>
                    <div className="barchart-row"><span className="bl">تناسب (fit)</span>
                      <div className="bt"><div style={{ width: m.fit + "%" }} /></div><span className="bv">{fa(m.fit)}٪</span></div>
                    <div className="barchart-row"><span className="bl">اطمینان به داده‌ها</span>
                      <div className="bt"><div style={{ width: m.confidence + "%", background: "var(--grad-teal)" }} /></div><span className="bv">{fa(m.confidence)}٪</span></div>
                  </div>
                  <div style={{ fontSize: 12.5 }}>
                    {m.evidence?.length > 0 && <div>✓ شواهد تأییدشده: {m.evidence.join("، ")}</div>}
                    {m.gaps?.length > 0 && <div className="muted">△ شکاف: {m.gaps.join("، ")}</div>}
                    <div className="muted">⏱ ظرفیت: {m.capacity?.note}</div>
                    <div className="muted">↔ {m.two_way_note}</div>
                  </div>
                </div>
              </div>
            ))}
            <div className="detail-grid" style={{ margin: "8px 0" }}>
              <dt className="muted">پوشش تجمعی</dt><dd>{t.coverage?.covered?.join("، ") || "—"}</dd>
              <dt className="muted">شکاف باقی‌مانده</dt><dd>{t.coverage?.missing?.join("، ") || "—"}</dd>
            </div>
            {(t.resource_notes || []).map((n: string, i: number) => <div key={i} className="alert warn">• {n}</div>)}
            {canManage && t.status === "proposed" && (
              <button className="btn ok" disabled={busy} onClick={() => accept(t.id)}>پذیرش تیم و ساخت همکاری ✓</button>
            )}
            {t.project_id && <button className="btn" onClick={() => nav("/collaboration/" + t.project_id)}>مشاهده همکاری ←</button>}
          </div>
        ))}
      </Card>
    </div>
  );
}
