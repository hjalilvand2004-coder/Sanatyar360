// فرم چندمرحله‌ای ثبت مسئله (شناسنامه ← شرح ← ظرفیت ← اجرا ← مالی ← حقوقی/زمان)
import React, { useEffect, useState } from "react";
import { api, label } from "../api";
import { Card, Alert, Field } from "../ui";
import { useApp } from "../App";

const STEPS = ["شناسنامه", "شرح و خروجی", "ظرفیت موردنیاز", "اجرا و منابع", "مالی", "حقوقی و زمان"];
const EMPTY = {
  title: "", summary: "", description: "", category: "", industry_code: "MAN-01",
  expected_outcomes: "", acceptance_criteria: "", skill_names: "", required_team_size: 2,
  duration_days: 90, work_mode: "hybrid", location: "", resources_offered: "",
  budget_min: "", budget_max: "", currency: "IRR", budget_confirmed: false,
  confidentiality_level: "public", ip_policy_summary: "", nda_required: false,
  application_deadline: "", desired_start: "", contact_name: "", contact_channel: "",
};

export default function ProblemNew({ route }: any) {
  const { me, nav, notify } = useApp();
  const editId = new URLSearchParams((route.split("?")[1] || "")).get("edit");
  const [step, setStep] = useState(0);
  const [f, setF] = useState<any>(EMPTY);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k: string, v: any) => setF((x: any) => ({ ...x, [k]: v }));

  useEffect(() => {
    if (editId) {
      api("/problems/" + editId).then((p) => setF({
        ...EMPTY, ...p,
        expected_outcomes: (p.expected_outcomes || []).join("\n"),
        acceptance_criteria: (p.acceptance_criteria || []).join("\n"),
        skill_names: (p.required_skills_full || []).map((s: any) => s.skill).join("، "),
        application_deadline: (p.application_deadline || "").slice(0, 10),
      }));
    } else if (me.memberships[0]) {
      const rep = me.memberships.find((m: any) => ["industry_rep", "industry_manager"].includes(m.role));
      if (rep) set("contact_name", me.user.full_name);
    }
  }, [editId]);

  const submit = async (send: boolean) => {
    setErr(""); setBusy(true);
    try {
      const body = {
        ...f,
        budget_min: f.budget_min ? +f.budget_min : null,
        budget_max: f.budget_max ? +f.budget_max : null,
        duration_days: f.duration_days ? +f.duration_days : null,
        required_team_size: +f.required_team_size,
        expected_outcomes: f.expected_outcomes.split("\n").map((x: string) => x.trim()).filter(Boolean),
        acceptance_criteria: f.acceptance_criteria.split("\n").map((x: string) => x.trim()).filter(Boolean),
        skill_names: f.skill_names.split(/[،,]/).map((x: string) => x.trim()).filter(Boolean),
        application_deadline: f.application_deadline ? new Date(f.application_deadline).toISOString() : null,
      };
      const d = editId
        ? await api("/problems/" + editId, { method: "PATCH", body })
        : await api("/problems", { method: "POST", body });
      if (send) await api("/problems/" + d.id + "/submit", { method: "POST" });
      notify(send ? "مسئله ثبت و برای بررسی ارسال شد" : "پیش‌نویس ذخیره شد");
      nav("/problem/" + d.id);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  if (!me.memberships.some((m: any) => ["industry_rep", "industry_manager"].includes(m.role)))
    return <Alert kind="error">ثبت مسئله فقط برای نماینده صنعت / مدیر سازمان صنعتی مجاز است.</Alert>;

  return (
    <div>
      {err && <Alert kind="error">{err}</Alert>}
      <Card title={"مرحله " + (step + 1) + " از ۶ — " + STEPS[step]}>
        <div className="flow" style={{ marginBottom: 16 }}>
          {STEPS.map((s, i) => <span key={s} className={"fs " + (i === step ? "now" : i < step ? "done" : "")}>{s}</span>)}
        </div>
        {step === 0 && (
          <div>
            <Field label="عنوان مسئله"><input value={f.title} onChange={(e: any) => set("title", e.target.value)} placeholder="مثلاً بهینه‌سازی مصرف انرژی خط تولید" /></Field>
            <Field label="خلاصه عمومی" hint="این خلاصه حتی برای سطوح محرمانه نمایش داده می‌شود؛ اطلاعات حساس ننویسید">
              <textarea value={f.summary} onChange={(e: any) => set("summary", e.target.value)} /></Field>
            <div className="grid cols-2">
              <Field label="دسته مسئله"><input value={f.category} onChange={(e: any) => set("category", e.target.value)} placeholder="مثلاً انرژی و بهره‌وری" /></Field>
              <Field label="حوزه صنعت">
                <select value={f.industry_code} onChange={(e: any) => set("industry_code", e.target.value)}>
                  <option value="MAN-01">ماشین‌سازی و اتوماسیون (MAN-01)</option>
                  <option value="MET-02">فلزات (MET-02)</option>
                </select></Field>
            </div>
          </div>
        )}
        {step === 1 && (
          <div>
            <Field label="وضعیت موجود، مسئله اصلی، پیامد و هدف"><textarea style={{ minHeight: 140 }} value={f.description} onChange={(e: any) => set("description", e.target.value)} /></Field>
            <Field label="تحویل‌دادنی‌های مورد انتظار (هر خط یک مورد)"><textarea value={f.expected_outcomes} onChange={(e: any) => set("expected_outcomes", e.target.value)} /></Field>
            <Field label="معیار پذیرش (هر خط یک مورد)" hint="قابل اندازه‌گیری باشد؛ انتشار بدون معیار پذیرش رد می‌شود (AC-02)">
              <textarea value={f.acceptance_criteria} onChange={(e: any) => set("acceptance_criteria", e.target.value)} /></Field>
          </div>
        )}
        {step === 2 && (
          <div>
            <Field label="مهارت‌های موردنیاز (با «،» جدا کنید)"><input value={f.skill_names} onChange={(e: any) => set("skill_names", e.target.value)} placeholder="تحلیل داده، Python، یادگیری ماشین" /></Field>
            <div className="grid cols-2">
              <Field label="تعداد افراد موردنیاز"><input type="number" value={f.required_team_size} onChange={(e: any) => set("required_team_size", e.target.value)} /></Field>
              <Field label="مدت تخمینی (روز)"><input type="number" value={f.duration_days} onChange={(e: any) => set("duration_days", e.target.value)} /></Field>
            </div>
          </div>
        )}
        {step === 3 && (
          <div>
            <div className="grid cols-2">
              <Field label="نوع اجرا">
                <select value={f.work_mode} onChange={(e: any) => set("work_mode", e.target.value)}>
                  {["hybrid", "onsite", "remote"].map((x) => <option key={x} value={x}>{label(x)}</option>)}
                </select></Field>
              <Field label="محل اجرا"><input value={f.location} onChange={(e: any) => set("location", e.target.value)} /></Field>
            </div>
            <Field label="تجهیزات/داده/امکانات قابل ارائه"><textarea value={f.resources_offered} onChange={(e: any) => set("resources_offered", e.target.value)} /></Field>
            <Field label="مسئول پاسخ‌گویی و روش ارتباط مجاز">
              <div className="grid cols-2">
                <input value={f.contact_name} onChange={(e: any) => set("contact_name", e.target.value)} placeholder="نام مسئول" />
                <input value={f.contact_channel} onChange={(e: any) => set("contact_channel", e.target.value)} placeholder="مثلاً ایمیل از طریق سامانه" />
              </div></Field>
          </div>
        )}
        {step === 4 && (
          <div>
            <div className="grid cols-3">
              <Field label="حداقل بودجه (ریال)"><input type="number" value={f.budget_min} onChange={(e: any) => set("budget_min", e.target.value)} /></Field>
              <Field label="حداکثر بودجه (ریال)"><input type="number" value={f.budget_max} onChange={(e: any) => set("budget_max", e.target.value)} /></Field>
              <Field label="وضعیت قطعیت بودجه">
                <select value={f.budget_confirmed ? "1" : "0"} onChange={(e: any) => set("budget_confirmed", e.target.value === "1")}>
                  <option value="1">قطعی</option><option value="0">غیرقطعی/در حال تخصیص</option>
                </select></Field>
            </div>
          </div>
        )}
        {step === 5 && (
          <div>
            <div className="grid cols-2">
              <Field label="سطح محرمانگی" hint="مسائل محرمانه فقط برای سازمان مالک و دفتر نمایش داده می‌شود">
                <select value={f.confidentiality_level} onChange={(e: any) => set("confidentiality_level", e.target.value)}>
                  {["public", "registered_users", "selected_participants", "confidential"].map((x) => <option key={x} value={x}>{label(x)}</option>)}
                </select></Field>
              <Field label="نیاز به NDA">
                <select value={f.nda_required ? "1" : "0"} onChange={(e: any) => set("nda_required", e.target.value === "1")}>
                  <option value="0">خیر</option><option value="1">بله — پیش از دسترسی به جزئیات</option>
                </select></Field>
            </div>
            <Field label="شرایط مالکیت فکری (خلاصه)"><textarea value={f.ip_policy_summary} onChange={(e: any) => set("ip_policy_summary", e.target.value)} /></Field>
            <div className="grid cols-2">
              <Field label="مهلت درخواست (تاریخ میلادی)">
                <input type="date" value={f.application_deadline} onChange={(e: any) => set("application_deadline", e.target.value)} /></Field>
              <Field label="شروع مطلوب"><input value={f.desired_start} onChange={(e: any) => set("desired_start", e.target.value)} /></Field>
            </div>
          </div>
        )}
        <div className="btn-row" style={{ marginTop: 18 }}>
          {step > 0 && <button className="btn" onClick={() => setStep(step - 1)}>مرحله قبل</button>}
          {step < 5 && <button className="btn primary" onClick={() => setStep(step + 1)}>مرحله بعد</button>}
          <span style={{ flex: 1 }} />
          <button className="btn" disabled={busy} onClick={() => submit(false)}>ذخیره پیش‌نویس</button>
          <button className="btn primary" disabled={busy} onClick={() => submit(true)}>ذخیره و ارسال برای بررسی</button>
        </div>
      </Card>
    </div>
  );
}
