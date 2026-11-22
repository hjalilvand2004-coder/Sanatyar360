// جزئیات همکاری: نقاط عطف، خروجی‌ها و پذیرش، تغییر وضعیت، ارزیابی، دستاورد
import React, { useEffect, useState } from "react";
import { api, jalali, statusBadge, label, fa } from "../api";
import { Card, Empty, Alert, Modal, Field } from "../ui";
import { useApp } from "../App";

export default function CollabDetail({ route }: any) {
  const id = route.slice("/collaboration/".length);
  const { me, notify } = useApp();
  const [p, setP] = useState<any>(null);
  const [err, setErr] = useState("");
  const [modal, setModal] = useState<"" | "milestone" | "deliverable" | "status" | "evaluate" | "achievement" | "pilot" | "pilotDecision" | "change">("");

  const load = () => api("/collaborations/" + id).then(setP).catch((e: any) => setErr(e.message));
  useEffect(load, [id]);

  if (err) return <Alert kind="error">{err}</Alert>;
  if (!p) return <Empty text="در حال بارگذاری…" />;
  const pilotP = p.pilot;

  const myOrgs = new Set(me.memberships.map((m: any) => m.organization_id));
  const isIndustryRep = me.memberships.some((m: any) => m.organization_id === p.industry_org?.id && ["industry_rep", "industry_manager"].includes(m.role));
  const isAcademicSide = myOrgs.has(p.university_org?.id) || p.members.some((m: any) => m.user.id === me.user.id && me.user.user_type !== "industry");
  const canDecideStatus = isIndustryRep || isAcademicSide;
  const submittedDels = p.deliverables.filter((d: any) => d.status === "submitted");

  return (
    <div>
      {err && <Alert kind="error">{err}</Alert>}
      <Card title={p.title + " — " + p.code} extra={statusBadge(p.status)}>
        <dl className="detail-grid">
          <dt>سازمان صنعتی</dt><dd>{p.industry_org?.name}</dd>
          <dt>دانشگاه</dt><dd>{p.university_org?.name || "—"}</dd>
          <dt>مسئول علمی</dt><dd>{p.academic_lead?.full_name || "—"}</dd>
          <dt>نماینده صنعت</dt><dd>{p.industry_rep?.full_name || "—"}</dd>
          <dt>مسئله مبدأ</dt><dd>{p.problem_title || "—"} {p.problem_id && <a href={"#/problem/" + p.problem_id}>مشاهده</a>}</dd>
          <dt>محدوده کار</dt><dd>{p.scope || "—"}</dd>
          <dt>معیار پذیرش توافق‌شده</dt><dd>{p.acceptance_summary || "—"}</dd>
          <dt>قرارداد / NDA</dt><dd>{p.agreement_ref || "ثبت نشده ⚠️"} / {p.nda_ref || "—"}</dd>
          <dt>شناسه در سامانه پروژه</dt><dd>{p.external_project_id || "—"}</dd>
          <dt>شروع</dt><dd>{jalali(p.started_at, true)}</dd>
          {p.status_note && <><dt>یادداشت وضعیت</dt><dd>{p.status_note}</dd></>}
          {p.final_achievement && <><dt>دستاورد نهایی</dt><dd style={{ background: "rgba(52,211,153,0.12)", padding: 8, borderRadius: 8 }}>{p.final_achievement}</dd></>}
        </dl>
        <div className="btn-row" style={{ marginTop: 14 }}>
          <button className="btn sm" onClick={() => setModal("milestone")}>＋ نقطه عطف</button>
          {!p.pilot && (isIndustryRep || isAcademicSide) && <button className="btn sm primary" onClick={() => setModal("pilot")}>🧪 تعریف پایلوت</button>}
          {isIndustryRep && <button className="btn sm" onClick={() => setModal("change")}>＋ درخواست تغییر</button>}
          {isAcademicSide && ["active", "on_hold"].includes(p.status) && <button className="btn sm primary" onClick={() => setModal("deliverable")}>ثبت خروجی</button>}
          {canDecideStatus && <button className="btn sm" onClick={() => setModal("status")}>تغییر وضعیت پروژه</button>}
          <button className="btn sm" onClick={() => setModal("achievement")}>ثبت/ویرایش دستاورد نهایی</button>
          <button className="btn sm" onClick={() => setModal("evaluate")}>ارزیابی همکاری</button>
        </div>
        {p.status === "agreement_pending" && (
          <Alert kind="warn">پروژه در انتظار توافق است؛ پس از ثبت قرارداد، وضعیت را به «فعال» تغییر دهید. پذیرش Checkbox جایگزین قرارداد حقوقی نیست.</Alert>
        )}
        {!p.pilot && isAcademicSide && ["proposed", "agreement_pending"].includes(p.status) && (
          <Alert kind="info">پیشنهاد: پیش از قرارداد اصلی، یک <b>پایلوت کوتاه</b> تعریف کنید — ریسک صنعت را کم می‌کند و ارزیابی توان تیم واقعی‌تر می‌شود.</Alert>
        )}
      </Card>

      {p.pilot && (
        <Card title="🧪 پایلوت — اثبات امکان‌پذیری پیش از قرارداد اصلی">
          <div className="detail-grid">
            <dt>عنوان</dt><dd><b>{p.pilot.title}</b></dd>
            <dt>محدوده</dt><dd>{p.pilot.scope || "—"}</dd>
            <dt>بازهٔ زمانی</dt><dd>{p.pilot.start_date || "—"} تا {p.pilot.end_date || "—"}</dd>
            <dt>بودجهٔ مستقل</dt><dd>{p.pilot.budget_note || "—"}</dd>
            <dt>خروجی قابل‌آزمایش</dt><dd>{p.pilot.acceptance_test || "—"}</dd>
            {p.pilot.decision ? (
              <>
                <dt>سنجهٔ نتیجه</dt><dd>{p.pilot.outcome_metric || "—"} = <b>{p.pilot.outcome_value || "—"}</b></dd>
                <dt>تصمیم</dt><dd>{p.pilot.decision === "continue" ? "✅ ادامه (پایلوت موفق)" : p.pilot.decision === "adjust" ? "🔧 اصلاح و ادامه" : "⛔ توقف"} <span className="muted">{p.pilot.decision_note}</span></dd>
              </>
            ) : (
              <><dt>وضعیت</dt><dd>در حال اجرا — پس از پایان، سنجه و تصمیم را ثبت کنید</dd></>
            )}
          </div>
          {isIndustryRep && !p.pilot.decision && (
            <button className="btn primary" style={{ marginTop: 10 }} onClick={() => setModal("pilotDecision")}>ثبت سنجهٔ نتیجه و تصمیم</button>
          )}
        </Card>
      )}

      {p.change_requests?.length > 0 && (
        <Card title="مدیریت تغییرات (دامنه/زمان/هزینه)">
          {p.change_requests.map((c: any) => (
            <div key={c.id} style={{ borderBottom: "1px solid var(--border)", paddingBottom: 10, marginBottom: 10 }}>
              <b>{c.field === "scope" ? "تغییر دامنه" : c.field === "schedule" ? "تغییر زمان‌بندی" : "تغییر بودجه"}</b> {statusBadge(c.status)}
              <div>{c.new_value}</div>
              {c.justification && <div className="muted">دلیل: {c.justification}</div>}
              {c.decision_note && <div className="muted">یادداشت تصمیم: {c.decision_note}</div>}
            </div>
          ))}
        </Card>
      )}

      <div className="grid cols-2">
        <Card title="نقاط عطف">
          {p.milestones.length === 0 ? <Empty /> : (
            <div className="timeline">{p.milestones.map((m: any) => (
              <div key={m.id} className="step">
                <b>{m.title}</b> {statusBadge(m.status)}
                <div className="when">مهلت: {m.due_date || "—"} {m.completed_at && "| انجام: " + jalali(m.completed_at, true)}</div>
              </div>
            ))}</div>
          )}
        </Card>
        <Card title="خروجی‌ها و پذیرش (فقط نماینده صنعت مجاز به پذیرش — AC-09)">
          {p.deliverables.length === 0 ? <Empty /> : p.deliverables.map((d: any) => (
            <div key={d.id} style={{ borderBottom: "1px solid var(--border)", paddingBottom: 10, marginBottom: 10 }}>
              <b>{d.title}</b> {statusBadge(d.status)}
              <div className="muted">ثبت: {jalali(d.submitted_at, true)} {d.description ? "| " + d.description : ""}</div>
              {d.review_note && <div className="alert info" style={{ marginTop: 6 }}>نظر بررسی: {d.review_note}</div>}
              {isIndustryRep && d.status === "submitted" && (
                <div className="btn-row" style={{ marginTop: 6 }}>
                  <button className="btn sm ok" onClick={async () => { await api("/deliverables/" + d.id + "/reviews", { method: "POST", body: { decision: "accept", note: "پذیرش خروجی مطابق معیار" } }); notify("خروجی پذیرفته شد"); load(); }}>پذیرش</button>
                  <button className="btn sm warn" onClick={async () => { const note = prompt("دلیل درخواست اصلاح:"); if (note) { await api("/deliverables/" + d.id + "/reviews", { method: "POST", body: { decision: "revision_requested", note } }); load(); } }}>درخواست اصلاح</button>
                </div>
              )}
            </div>
          ))}
          {submittedDels.length > 0 && isIndustryRep && <div className="alert warn">{fa(submittedDels.length)} خروجی در انتظار تصمیم شماست.</div>}
        </Card>
      </div>

      <Card title="اعضا">
        <div className="chips">{p.members.map((m: any) => <span key={m.user.id} className="chip">{m.user.full_name} — {m.role}</span>)}</div>
      </Card>

      {p.evaluations.length > 0 && (
        <Card title="ارزیابی طرف‌ها">
          {p.evaluations.map((e: any, i: number) => (
            <div key={i}>{"★".repeat(e.rating)}{"☆".repeat(5 - e.rating)} — {e.comment || "بدون توضیح"} <span className="muted">({jalali(e.created_at)})</span></div>
          ))}
        </Card>
      )}

      {modal === "milestone" && <MilestoneModal id={id} onClose={() => setModal("")} onDone={() => { setModal(""); load(); }} />}
      {modal === "pilot" && <PilotModal id={id} onClose={() => setModal("")} onDone={() => { setModal(""); load(); }} />}
      {modal === "pilotDecision" && pilotP && <PilotDecisionModal pilot={pilotP} onClose={() => setModal("")} onDone={() => { setModal(""); load(); notify("نتیجهٔ پایلوت در شاخص‌های نتیجه ثبت شد"); }} />}
      {modal === "change" && <ChangeModal id={id} currentScope={p.scope} onClose={() => setModal("")} onDone={() => { setModal(""); load(); }} />}
      {modal === "deliverable" && <DeliverableModal id={id} milestones={p.milestones} onClose={() => setModal("")} onDone={() => { setModal(""); load(); }} />}
      {modal === "status" && <StatusModal id={id} status={p.status} hasAgreement={!!p.agreement_ref} achievement={p.final_achievement} onClose={() => setModal("")} onDone={() => { setModal(""); load(); }} />}
      {modal === "evaluate" && <EvaluateModal id={id} onClose={() => setModal("")} onDone={() => { setModal(""); load(); }} />}
      {modal === "achievement" && <AchievementModal id={id} value={p.final_achievement} onClose={() => setModal("")} onDone={() => { setModal(""); load(); }} />}
    </div>
  );
}

const MilestoneModal = ({ id, onClose, onDone }: any) => {
  const [f, setF] = useState({ title: "", due_date: "" });
  return (
    <Modal title="نقطه عطف جدید" onClose={onClose}>
      <Field label="عنوان"><input value={f.title} onChange={(e: any) => setF({ ...f, title: e.target.value })} /></Field>
      <Field label="مهلت (اختیاری)"><input value={f.due_date} onChange={(e: any) => setF({ ...f, due_date: e.target.value })} placeholder="۱۴۰۵/۱۰/۲۰" /></Field>
      <button className="btn primary" disabled={!f.title} onClick={async () => { await api(`/collaborations/${id}/milestones`, { method: "POST", body: f }); onDone(); }}>ثبت</button>
    </Modal>
  );
};

// ---------- پایلوت و مدیریت تغییرات (v1.1.0) ----------
const PilotModal = ({ id, onClose, onDone }: any) => {
  const [f, setF] = useState({ title: "", scope: "", start_date: "", end_date: "", budget_note: "", acceptance_test: "" });
  const [err, setErr] = useState("");
  const set = (k: string, v: string) => setF({ ...f, [k]: v });
  return (
    <Modal title="تعریف پایلوت — اثبات امکان‌پذیری" onClose={onClose}>
      {err && <Alert kind="error">{err}</Alert>}
      <Alert kind="info">مسئله محدود و مشخص، زمان کوتاه و توافق‌شده، بودجه مستقل و خروجی قابل‌آزمایش — سپس تصمیم: ادامه، اصلاح یا توقف.</Alert>
      <Field label="عنوان پایلوت"><input value={f.title} onChange={(e: any) => set("title", e.target.value)} placeholder="مثلاً اثبات دقت تشخیص عیب روی نمونه‌ها" /></Field>
      <Field label="محدودهٔ محدود و مشخص"><textarea value={f.scope} onChange={(e: any) => set("scope", e.target.value)} /></Field>
      <div className="grid cols-2">
        <Field label="شروع"><input value={f.start_date} onChange={(e: any) => set("start_date", e.target.value)} placeholder="۱۴۰۵/۰۹/۰۱" /></Field>
        <Field label="پایان (کوتاه!)"><input value={f.end_date} onChange={(e: any) => set("end_date", e.target.value)} placeholder="۱۴۰۵/۰۹/۲۵" /></Field>
      </div>
      <Field label="بودجهٔ مستقل"><input value={f.budget_note} onChange={(e: any) => set("budget_note", e.target.value)} placeholder="مثلاً ۳۰ میلیون تومان — جدا از قرارداد اصلی" /></Field>
      <Field label="خروجی قابل‌آزمایش + معیار پذیرش"><textarea value={f.acceptance_test} onChange={(e: any) => set("acceptance_test", e.target.value)} placeholder="مثلاً دقت بالای ۸۵٪ روی ۲۰۰ تصویر تست" /></Field>
      <button className="btn primary" disabled={!f.title} onClick={async () => {
        try { await api(`/collaborations/${id}/pilot`, { method: "POST", body: f }); onDone(); }
        catch (e: any) { setErr(e.message); }
      }}>ثبت پایلوت</button>
    </Modal>
  );
};

const PilotDecisionModal = ({ pilot, onClose, onDone }: any) => {
  const [f, setF] = useState({ decision: "continue", decision_note: "", outcome_metric: pilot.outcome_metric || "", outcome_value: "" });
  const [err, setErr] = useState("");
  const set = (k: string, v: string) => setF({ ...f, [k]: v });
  return (
    <Modal title="سنجهٔ نتیجه و تصمیم پایلوت" onClose={onClose}>
      {err && <Alert kind="error">{err}</Alert>}
      <Field label="سنجهٔ نتیجه (قابل‌اندازه‌گیری)"><input value={f.outcome_metric} onChange={(e: any) => set("outcome_metric", e.target.value)} placeholder="مثلاً دقت تشخیص عیب" /></Field>
      <Field label="مقدار اندازه‌گیری‌شده و تأییدشدهٔ صنعت"><input value={f.outcome_value} onChange={(e: any) => set("outcome_value", e.target.value)} placeholder="مثلاً ۹۲٪ — تأیید سرپرست خط" /></Field>
      <Field label="تصمیم نهایی">
        <select value={f.decision} onChange={(e: any) => set("decision", e.target.value)}>
          <option value="continue">ادامه → قرارداد اصلی</option>
          <option value="adjust">اصلاح و ادامه</option>
          <option value="stop">توقف</option>
        </select></Field>
      <Field label="یادداشت تصمیم"><textarea value={f.decision_note} onChange={(e: any) => set("decision_note", e.target.value)} /></Field>
      <button className="btn primary" disabled={!f.outcome_value} onClick={async () => {
        try { await api(`/pilots/${pilot.id}/decision`, { method: "POST", body: f }); onDone(); }
        catch (e: any) { setErr(e.message); }
      }}>ثبت تصمیم</button>
    </Modal>
  );
};

const ChangeModal = ({ id, currentScope, onClose, onDone }: any) => {
  const [f, setF] = useState({ field: "scope", new_value: "", old_value: "", justification: "" });
  const [err, setErr] = useState("");
  const set = (k: string, v: string) => setF({ ...f, [k]: v });
  return (
    <Modal title="درخواست تغییر (دامنه/زمان/هزینه)" onClose={onClose}>
      {err && <Alert kind="error">{err}</Alert>}
      <Field label="نوع تغییر">
        <select value={f.field} onChange={(e: any) => set("field", e.target.value)}>
          <option value="scope">دامنه کار</option>
          <option value="schedule">زمان‌بندی</option>
          <option value="budget">بودجه</option>
        </select></Field>
      {f.field === "scope" && <Field label="مقدار فعلی"><textarea value={f.old_value} onChange={(e: any) => set("old_value", e.target.value)} placeholder={currentScope || "—" } /></Field>}
      <Field label="مقدار جدید"><textarea value={f.new_value} onChange={(e: any) => set("new_value", e.target.value)} /></Field>
      <Field label="دلیل تغییر"><textarea value={f.justification} onChange={(e: any) => set("justification", e.target.value)} /></Field>
      <button className="btn primary" disabled={!f.new_value} onClick={async () => {
        try { await api(`/collaborations/${id}/change-requests`, { method: "POST", body: f }); onDone(); }
        catch (e: any) { setErr(e.message); }
      }}>ثبت درخواست (در انتظار تأیید طرف مقابل)</button>
    </Modal>
  );
};

const DeliverableModal = ({ id, milestones, onClose, onDone }: any) => {
  const [f, setF] = useState({ title: "", description: "", milestone_id: "" });
  return (
    <Modal title="ثبت خروجی" onClose={onClose}>
      <Field label="عنوان خروجی"><input value={f.title} onChange={(e: any) => setF({ ...f, title: e.target.value })} /></Field>
      <Field label="توضیح"><textarea value={f.description} onChange={(e: any) => setF({ ...f, description: e.target.value })} /></Field>
      <Field label="نقطه عطف مرتبط">
        <select value={f.milestone_id} onChange={(e: any) => setF({ ...f, milestone_id: e.target.value })}>
          <option value="">— بدون اتصال —</option>
          {milestones.filter((m: any) => m.status !== "done").map((m: any) => <option key={m.id} value={m.id}>{m.title}</option>)}
        </select></Field>
      <button className="btn primary" disabled={!f.title} onClick={async () => { await api(`/collaborations/${id}/deliverables`, { method: "POST", body: f }); onDone(); }}>ثبت و ارسال برای پذیرش</button>
    </Modal>
  );
};

const StatusModal = ({ id, status, hasAgreement, achievement, onClose, onDone }: any) => {
  const options: Record<string, string[]> = {
    proposed: ["agreement_pending", "terminated"],
    agreement_pending: ["active", "terminated"],
    active: ["on_hold", "completed", "terminated"],
    on_hold: ["active", "completed", "terminated"],
  };
  const [s, setS] = useState(options[status]?.[0] || "");
  const [note, setNote] = useState("");
  const [ach, setAch] = useState(achievement || "");
  const [err, setErr] = useState("");
  const go = async () => {
    setErr("");
    try { await api(`/collaborations/${id}/status`, { method: "POST", body: { status: s, note, final_achievement: ach || undefined } }); onDone(); }
    catch (e: any) { setErr(e.message); }
  };
  return (
    <Modal title="تغییر وضعیت پروژه همکاری" onClose={onClose}>
      {err && <Alert kind="error">{err}</Alert>}
      <Field label="وضعیت جدید">
        <select value={s} onChange={(e: any) => setS(e.target.value)}>
          {(options[status] || []).map((x: string) => <option key={x} value={x}>{label(x)}</option>)}
        </select></Field>
      {(s === "active" && !hasAgreement) && <Alert kind="warn">هشدار: قراردادی ثبت نشده؛ پیشنهاد می‌شود ابتدا شماره قرارداد را از طریق دفتر ثبت کنید.</Alert>}
      {s === "completed" && <Field label="دستاورد نهایی (الزامی برای تکمیل)"><textarea value={ach} onChange={(e: any) => setAch(e.target.value)} /></Field>}
      <Field label="یادداشت (برای خاتمه الزامی)"><textarea value={note} onChange={(e: any) => setNote(e.target.value)} /></Field>
      <button className="btn primary" onClick={go}>ثبت تغییر وضعیت</button>
    </Modal>
  );
};

const EvaluateModal = ({ id, onClose, onDone }: any) => {
  const [rating, setRating] = useState(4);
  const [comment, setComment] = useState("");
  return (
    <Modal title="ارزیابی همکاری" onClose={onClose}>
      <Field label="امتیاز">
        <select value={rating} onChange={(e: any) => setRating(+e.target.value)}>
          {[1, 2, 3, 4, 5].map((x) => <option key={x} value={x}>{"★".repeat(x)}</option>)}
        </select></Field>
      <Field label="توضیح"><textarea value={comment} onChange={(e: any) => setComment(e.target.value)} /></Field>
      <button className="btn primary" onClick={async () => { await api(`/collaborations/${id}/evaluations`, { method: "POST", body: { rating, comment } }); onDone(); }}>ثبت ارزیابی</button>
    </Modal>
  );
};

const AchievementModal = ({ id, value, onClose, onDone }: any) => {
  const [v, setV] = useState(value || "");
  return (
    <Modal title="دستاورد نهایی همکاری" onClose={onClose}>
      <Field label="شرح دستاورد" hint="پس از تکمیل، این متن در شاخص‌های اثر همکاری لحاظ می‌شود"><textarea value={v} onChange={(e: any) => setV(e.target.value)} /></Field>
      <button className="btn primary" disabled={v.length < 10} onClick={async () => { await api(`/collaborations/${id}/achievement`, { method: "PATCH", body: { final_achievement: v } }); onDone(); }}>ثبت</button>
    </Modal>
  );
};
