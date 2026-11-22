// دستیار «از نیاز صنعتی تا پروژه» — پرسش‌گری راهنما، پیش‌نویس استاندارد، تأیید انسانی
import React, { useEffect, useState } from "react";
import { useApp } from "../App";
import { api } from "../api";

const FIELD_LABELS: Record<string, string> = {
  need_text: "نیاز اولیه (عین گفتهٔ صنعت)",
  current_state: "وضعیت موجود",
  real_pain: "مشکل واقعی و هزینهٔ آن",
  data_assets: "داده، تجهیزات و دسترسی‌ها",
  measurable_outcome: "نتیجهٔ مطلوب و نحوهٔ اندازه‌گیری",
  success_criteria: "خروجی نهایی مورد انتظار",
  constraints: "محدودیت‌ها (بودجه/زمان/محرمانگی)",
};

export default function Assistant() {
  const { nav, notify, me } = useApp() as any;
  const [step, setStep] = useState(0);
  const [questions, setQuestions] = useState<any[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState<any>(null);
  const [intakeId, setIntakeId] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [myIntakes, setMyIntakes] = useState<any[]>([]);

  useEffect(() => {
    api("/assistant/questions").then((d: any) => setQuestions(d.questions || [])).catch(() => {});
    api("/assistant/intakes").then((d: any) => setMyIntakes(d.items || [])).catch(() => {});
  }, []);

  const setA = (k: string, v: string) => setAnswers((p) => ({ ...p, [k]: v }));
  const filled = questions.filter((q) => (answers[q.key] || "").trim()).length;
  const canBuild = questions.length > 0 && filled >= Math.ceil(questions.length * 0.6);

  const build = async () => {
    setBusy(true); setErr("");
    try {
      const d = await api("/assistant/intakes", { method: "POST", body: { answers } });
      setDraft(d.draft); setIntakeId(d.id); setStep(99);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };

  const confirm = async () => {
    setBusy(true); setErr("");
    try {
      const d = await api(`/assistant/intakes/${intakeId}/confirm`, { method: "POST" });
      notify("مسئله از پیش‌نویس ساخته شد — در صف بررسی و انتشار");
      nav(`/problem/${d.problem_id}`);
    } catch (e: any) { setErr(e.message); setBusy(false); }
  };

  const loadOld = async (id: string) => {
    try {
      const d = await api(`/assistant/intakes/${id}`);
      setDraft(d.draft); setIntakeId(id); setStep(99);
    } catch (e: any) { setErr(e.message); }
  };

  if (step < 99) {
    const q = questions[step];
    return (
      <div style={{ maxWidth: 720 }}>
        <div className="card">
          <h3>✨ از نیاز صنعتی تا پروژه — پرسش‌گری راهنما</h3>
          <p className="muted" style={{ fontSize: 13 }}>
            بسیاری از شرکت‌ها مسئله‌شان را دقیق بیان نمی‌کنند. با پاسخ به چند سؤال، نیاز خود را به
            یک «مسئلهٔ اجرایی» استاندارد تبدیل کنید: دامنه، خروجی قابل‌تحویل، معیار پذیرش و مهارت‌های لازم.
          </p>
          <div className="progress" style={{ marginBottom: 16 }}><div style={{ width: `${questions.length ? (step / questions.length) * 100 : 5}%` }} /></div>
          {err && <div className="alert error">{err}</div>}
          {q && (
            <>
              <div className="field">
                <label>{step + 1}. {q.question}</label>
                <textarea value={answers[q.key] || ""}
                  onChange={(e: any) => setA(q.key, e.target.value)}
                  placeholder={q.optional ? "(اختیاری)" : "پاسخ را همین‌طور که هست بنویسید…"} />
              </div>
              <div className="btn-row" style={{ justifyContent: "space-between" }}>
                <button className="btn" disabled={step === 0} onClick={() => setStep(step - 1)}>قبلی</button>
                <span className="muted" style={{ fontSize: 12 }}>{filled}/{questions.length} پاسخ</span>
                {step < questions.length - 1
                  ? <button className="btn primary" onClick={() => setStep(step + 1)}>بعدی ←</button>
                  : <button className="btn primary" disabled={!canBuild || busy} onClick={build}>
                      {busy ? "در حال ساخت…" : "ساخت پیش‌نویس مسئله ✦"}</button>}
              </div>
            </>
          )}
          {!canBuild && step === questions.length - 1 && (
            <div className="alert info">برای ساخت پیش‌نویس، حداقل {Math.ceil(questions.length * 0.6)} سؤال را پاسخ دهید — کیفیت پیش‌نویس به پاسخ‌ها وابسته است.</div>
          )}
        </div>
        {myIntakes.length > 0 && (
          <div className="card">
            <h3>پیش‌نویس‌های قبلی</h3>
            {myIntakes.map((i) => (
              <button key={i.id} className="demo-acc" style={{ marginBottom: 6 }}
                onClick={() => loadOld(i.id)}>
                <span><b>{i.title || "بدون عنوان"}</b><br />
                  <small className="muted">{i.status === "confirmed" ? "نهایی‌شده ✓" : "پیش‌نویس"} · اطمینان داده: {i.confidence}٪</small></span>
                <span className="muted">مشاهده ←</span>
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }

  // ---------- نمایش پیش‌نویس ----------
  const est = draft.estimate || {};
  return (
    <div style={{ maxWidth: 780 }}>
      <div className="card">
        <h3>📄 پیش‌نویس استاندارد مسئله</h3>
        <div className="alert info">
          این پیش‌نویس توسط دستیار و بر مبنای پاسخ‌های شما تولید شده است؛ <b>تأیید کارشناس</b> پیش از
          انتشار لازم است و برآوردها قطعی نیستند.
        </div>
        <h3 style={{ marginTop: 4 }}>{draft.title}</h3>
        <div className="detail-grid">
          <dt className="muted">مشکل اصلی</dt><dd>{draft.scope?.problem_statement || "—"}</dd>
          <dt className="muted">وضعیت موجود</dt><dd>{draft.scope?.current_state || "—"}</dd>
          <dt className="muted">خروجی قابل‌تحویل</dt><dd>{draft.deliverable}</dd>
          <dt className="muted">معیار پذیرش</dt><dd>
            {(draft.acceptance_criteria || []).map((c: string, i: number) => <div key={i}>✓ {c}</div>)}
          </dd>
          <dt className="muted">مهارت‌های لازم</dt><dd>
            <div className="chips">{(draft.required_skills || []).map((s: string) =>
              <span key={s} className="chip">{s}</span>)}</div>
          </dd>
          <dt className="muted">اطمینان به داده‌ها</dt><dd>{draft.data_confidence}٪ از پرسش‌ها پاسخ داده شده است</dd>
        </div>
        {(draft.missing_info || []).length > 0 && (
          <div className="alert warn" style={{ marginTop: 12 }}>
            <b>اطلاعات ناقص — برای قضاوت کافی نیست:</b>
            {draft.missing_info.map((m: string, i: number) => <div key={i}>• {m}</div>)}
          </div>
        )}
        <div className="alert warn" style={{ marginTop: 10 }}>
          <b>برآورد (نیازمند تأیید کارشناس — وعده قطعی نیست):</b>
          <div>⏱ مدت پیشنهادی: حدود {est.duration_weeks} هفته</div>
          <div>💰 بازهٔ بودجهٔ راهنما: {est.budget_range_million_IRR?.[0]} تا {est.budget_range_million_IRR?.[1]} میلیون تومان</div>
          <small className="muted">{est.disclaimer}</small>
        </div>
        <div className="btn-row" style={{ marginTop: 12 }}>
          <button className="btn" onClick={() => { setDraft(null); setStep(0); }}>اصلاح پاسخ‌ها</button>
          <button className="btn primary" disabled={busy} onClick={confirm}>
            {busy ? "در حال ثبت…" : "تأیید و ساخت مسئله ✓ (تصمیم انسانی)"}
          </button>
        </div>
      </div>
    </div>
  );
}
