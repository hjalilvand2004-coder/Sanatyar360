// پرونده‌های فرصت تجاری‌سازی — غربالگری و ارزیابی متخصص (نه نتیجه قطعی)
import React, { useEffect, useState } from "react";
import { api, jalali, statusBadge, label } from "../api";
import { Card, Empty, Alert, Modal, Field } from "../ui";
import { useApp } from "../App";

export default function Commercialization() {
  const { me, notify } = useApp();
  const [cases, setCases] = useState<any[]>([]);
  const [modal, setModal] = useState<"" | "new" | "review">("");
  const [active, setActive] = useState<any>(null);

  const load = () => api("/commercialization/cases").then((d) => setCases(d.items)).catch(() => {});
  useEffect(load, []);

  const canCreate = me.memberships.some((m: any) =>
    ["cio_manager", "cio_expert", "comm_expert", "professor", "sys_admin"].includes(m.role));
  const canReview = me.memberships.some((m: any) => ["comm_expert", "cio_manager"].includes(m.role));

  return (
    <div>
      <Alert kind="warn">
        این بخش ابزار غربالگری و کمک به تصمیم متخصص است؛ نه مرجع قطعی ارزش‌گذاری، ثبت اختراع یا تشخیص قابلیت تجاری.
        بدون ثبت ارزیابی کارشناس تجاری‌سازی، هیچ پرونده‌ای «تأییدشده» تلقی نمی‌شود (AC-12).
      </Alert>
      {canCreate && <div className="btn-row" style={{ marginBottom: 14 }}>
        <button className="btn primary" onClick={() => setModal("new")}>＋ ثبت فرصت پیشنهادی</button>
      </div>}
      {cases.length === 0 ? <Card><Empty /></Card> : cases.map((c) => (
        <Card key={c.id} title={c.title} extra={statusBadge(c.status)}>
          <p style={{ margin: "4px 0 10px" }}>{c.rationale}</p>
          <b>شواهد قابل ردیابی:</b>
          <ul>{c.evidence?.map((e: any, i: number) => (
            <li key={i}>
              {e.claim} — <span className="muted">منبع: {e.source}</span>{" "}
              <span className={"badge " + (e.kind === "explicit" ? "green" : "amber")}>
                {e.kind === "explicit" ? "اطلاعات صریح" : "استنباط"}
              </span>
            </li>
          ))}</ul>
          {c.uncertainties && <div className="alert warn">ابهامات و داده‌های ناقص: {c.uncertainties}</div>}
          {c.market_signal && <div className="muted">سیگنال بازار: {c.market_signal}</div>}
          {c.reviews?.length > 0 && (
            <div style={{ marginTop: 8 }}><b>نظر کارشناس:</b>{c.reviews.map((r: any, i: number) => (
              <div key={i} className="muted">{r.expert} — {label(r.decision)} ({jalali(r.created_at)}) {r.comment ? "| " + r.comment : ""}</div>
            ))}</div>
          )}
          {canReview && !["expert_approved", "rejected"].includes(c.status) && (
            <button className="btn" style={{ marginTop: 8 }} onClick={() => { setActive(c); setModal("review"); }}>ثبت ارزیابی تخصصی</button>
          )}
        </Card>
      ))}

      {modal === "new" && <NewCaseModal onClose={() => setModal("")} onDone={() => { setModal(""); notify("پرونده ثبت شد و به کارشناس تجاری‌سازی اطلاع داده شد"); load(); }} />}
      {modal === "review" && active && <ReviewModal id={active.id} onClose={() => setModal("")} onDone={() => { setModal(""); load(); }} />}
    </div>
  );
}

const NewCaseModal = ({ onClose, onDone }: any) => {
  const [f, setF] = useState({ title: "", rationale: "", application_fields: "", evidence_text: "", uncertainties: "", market_signal: "" });
  const [err, setErr] = useState("");
  const set = (k: string, v: any) => setF({ ...f, [k]: v });
  const go = async () => {
    setErr("");
    // هر خط: ادعا | منبع | kind
    const evidence = f.evidence_text.split("\n").map((l) => {
      const [claim, source, kind] = l.split("|").map((x) => x?.trim());
      return claim ? { claim, source: source || "—", kind: kind === "استنباط" ? "inference" : "explicit" } : null;
    }).filter(Boolean);
    try {
      await api("/commercialization/cases", { method: "POST", body: {
        title: f.title, rationale: f.rationale,
        application_fields: f.application_fields.split("،").map((x) => x.trim()).filter(Boolean),
        evidence, uncertainties: f.uncertainties, market_signal: f.market_signal,
      }});
      onDone();
    } catch (e: any) { setErr(e.message); }
  };
  return (
    <Modal title="ثبت فرصت تجاری‌سازی پیشنهادی" onClose={onClose}>
      {err && <Alert kind="error">{err}</Alert>}
      <Field label="عنوان"><input value={f.title} onChange={(e: any) => set("title", e.target.value)} /></Field>
      <Field label="دلیل پیشنهاد (با ارجاع به شواهد)"><textarea value={f.rationale} onChange={(e: any) => set("rationale", e.target.value)} /></Field>
      <Field label="حوزه‌های کاربرد (با «،» جدا کنید)"><input value={f.application_fields} onChange={(e: any) => set("application_fields", e.target.value)} /></Field>
      <Field label="شواهد — هر خط: ادعا | منبع | نوع(صریح/استنباط)" hint="هر ادعا باید به منبع متصل شود؛ استنباط‌ها جدا برچسب می‌خورند">
        <textarea value={f.evidence_text} onChange={(e: any) => set("evidence_text", e.target.value)} placeholder={"دقت مدل F1=0.83 | گزارش پایلوت | صریح\nامکان فروش SaaS | روند آگهی‌های IoT | استنباط"} /></Field>
      <Field label="ابهامات و داده‌های ناقص"><textarea value={f.uncertainties} onChange={(e: any) => set("uncertainties", e.target.value)} /></Field>
      <Field label="سیگنال بازار"><input value={f.market_signal} onChange={(e: any) => set("market_signal", e.target.value)} /></Field>
      <button className="btn primary" disabled={f.title.length < 5 || f.rationale.length < 20} onClick={go}>ثبت پرونده</button>
    </Modal>
  );
};

const ReviewModal = ({ id, onClose, onDone }: any) => {
  const [f, setF] = useState({ need_fit_score: 3, trl_assessment: 5, market_evidence_score: 3, comment: "", next_action: "", decision: "proceed" });
  const set = (k: string, v: any) => setF({ ...f, [k]: v });
  const dims = [
    ["need_fit_score", "تناسب با نیاز واقعی (۱-۵)"],
    ["trl_assessment", "برآورد بلوغ فناوری TRL (۱-۹)"],
    ["market_evidence_score", "شواهد بازار (۱-۵)"],
  ];
  return (
    <Modal title="ارزیابی تخصصی فرصت" onClose={onClose}>
      {dims.map(([k, l]) => (
        <Field key={k} label={l as string}>
          <select value={f[k]} onChange={(e: any) => set(k as string, +e.target.value)}>
            {Array.from({ length: k === "trl_assessment" ? 9 : 5 }, (_, i) => i + 1).map((x) => (
              <option key={x} value={x}>{x.toLocaleString("fa-IR")}</option>))}
          </select></Field>
      ))}
      <Field label="وضعیت حقوقی/مالکیت و ظرفیت تیم — توضیح"><textarea value={f.comment} onChange={(e: any) => set("comment", e.target.value)} /></Field>
      <Field label="اقدام پیشنهادی بعدی"><input value={f.next_action} onChange={(e: any) => set("next_action", e.target.value)} /></Field>
      <Field label="تصمیم">
        <select value={f.decision} onChange={(e: any) => set("decision", e.target.value)}>
          <option value="proceed">ادامه فرآیند (پرونده تأیید متخصص)</option>
          <option value="need_info">نیازمند اطلاعات بیشتر</option>
          <option value="reject">رد</option>
        </select></Field>
      <button className="btn primary" onClick={async () => { await api(`/commercialization/cases/${id}/reviews`, { method: "POST", body: f }); onDone(); }}>ثبت ارزیابی</button>
    </Modal>
  );
};
