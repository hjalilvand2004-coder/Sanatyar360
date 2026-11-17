// جزئیات درخواست همکاری: دعوت اعضای تیم، پاسخ دعوت، تصمیم صنعت/دفتر
import React, { useEffect, useState } from "react";
import { api, jalali, statusBadge, label, fa } from "../api";
import { Card, Empty, Alert, Modal, Field } from "../ui";
import { useApp } from "../App";

export default function AppDetail({ route }: any) {
  const id = route.slice("/application/".length);
  const { me, nav, notify, userType } = useApp();
  const [a, setA] = useState<any>(null);
  const [err, setErr] = useState("");
  const [modal, setModal] = useState<"" | "invite" | "decide">("");
  const [users, setUsers] = useState<any[]>([]);

  const load = () => api("/applications/" + id).then(setA).catch((e: any) => setErr(e.message));
  useEffect(load, [id]);

  if (err) return <Alert kind="error">{err}</Alert>;
  if (!a) return <Empty text="در حال بارگذاری…" />;

  const isApplicant = a.applicant.id === me.user.id || (userType === "student" || userType === "professor") &&
    a.members.some((m: any) => m.user.id === me.user.id);
  const isIndustry = me.memberships.some((m: any) =>
    m.role === "industry_rep" || m.role === "industry_manager");
  const isCio = me.memberships.some((m: any) => ["cio_manager", "cio_expert"].includes(m.role));
  const invitedMe = a.members.find((m: any) => m.user.id === me.user.id && m.status === "invited");

  const decide = async (decision: string) => {
    setErr("");
    try { await api("/applications/" + id + "/decisions", { method: "POST", body: { decision, reason: (window as any).lastReason || undefined } }); notify("تصمیم ثبت شد"); load(); }
    catch (e: any) { setErr(e.message); }
  };

  return (
    <div>
      {err && <Alert kind="error">{err}</Alert>}
      <Card title={"درخواست همکاری — " + a.problem_title} extra={statusBadge(a.status)}>
        <dl className="detail-grid">
          <dt>متقاضی اصلی</dt><dd><b>{a.applicant.full_name}</b> ({label(a.applicant.user_type)}) {a.profile_limited ? <span className="badge gray">پروفایل حداقلی — بدون رضایت اشتراک</span> : <span className="badge green">اطلاعات کامل — رضایت داده شده</span>}</dd>
          {a.profile_limited === false && <>
            <dt>ایمیل</dt><dd>{a.applicant.email}</dd>
            <dt>گروه/مقطع</dt><dd>{a.applicant.department || "—"} — {a.applicant.degree || "—"}</dd>
            <dt>سوابق مرتبط</dt><dd>{a.related_background || "—"}</dd>
            <dt>طرح اولیه حل</dt><dd>{a.initial_plan || "—"}</dd>
          </>}
          <dt>توضیح تناسب</dt><dd>{a.fit_statement}</dd>
          <dt>نقش پیشنهادی</dt><dd>{a.proposed_role || "—"}</dd>
          <dt>ظرفیت زمانی</dt><dd>{fa(a.weekly_hours)} ساعت در هفته — آماده از {a.available_from || "—"}</dd>
          <dt>تاریخ ثبت</dt><dd>{jalali(a.created_at, true)}</dd>
          {a.decision_reason && <><dt>دلیل تصمیم</dt><dd>{a.decision_reason}</dd></>}
        </dl>
        {a.skills?.length > 0 && <div className="chips" style={{ marginTop: 10 }}>
          {a.skills.map((s: any) => <span key={s.skill} className="chip">{s.skill} — سطح {fa(s.level)} ({label(s.source)})</span>)}
        </div>}
        {isApplicant && ["submitted", "under_review", "shortlisted"].includes(a.status) && (
          <div className="btn-row" style={{ marginTop: 14 }}>
            <button className="btn primary" onClick={() => { api("/users?q=").then((d) => setUsers(d.items)); setModal("invite"); }}>دعوت عضو به تیم</button>
            <button className="btn warn" onClick={async () => { await api("/applications/" + id + "/withdraw", { method: "POST" }); notify("درخواست پس گرفته شد"); load(); }}>پس‌گرفتن درخواست</button>
          </div>
        )}
        {invitedMe && (
          <div className="btn-row" style={{ marginTop: 14 }}>
            <Alert kind="warn">شما به این تیم دعوت شده‌اید — پذیرش یا عدم پذیرش دعوت:</Alert>
            <button className="btn ok" onClick={async () => { await api(`/applications/${id}/members/${invitedMe.id}/respond`, { method: "POST", body: { accept: true } }); notify("دعوت پذیرفته شد"); load(); }}>پذیرش دعوت</button>
            <button className="btn danger" onClick={async () => { await api(`/applications/${id}/members/${invitedMe.id}/respond`, { method: "POST", body: { accept: false } }); load(); }}>عدم پذیرش</button>
          </div>
        )}
        {(isIndustry || isCio) && ["submitted", "under_review", "shortlisted"].includes(a.status) && (
          <div className="btn-row" style={{ marginTop: 14 }}>
            <button className="btn" onClick={() => (window as any).lastReason = undefined || decide("shortlist")}>افزودن به فهرست کوتاه</button>
            <button className="btn ok" onClick={() => setModal("decide")}>ثبت تصمیم نهایی (پذیرش/عدم پذیرش)</button>
          </div>
        )}
      </Card>

      <Card title="اعضای تیم پیشنهادی">
        {a.members.length === 0 ? <Empty text="عضوی دعوت نشده است" /> : (
          <div className="tbl-wrap"><table className="tbl">
            <thead><tr><th>نام</th><th>نقش</th><th>وضعیت دعوت</th><th>مهارت‌ها</th></tr></thead>
            <tbody>
              {a.members.map((m: any) => (
                <tr key={m.id}>
                  <td><b>{m.user.full_name}</b> {m.profile_limited_hint}</td>
                  <td>{m.role || "عضو"}</td>
                  <td>{statusBadge(m.status)}</td>
                  <td>{m.skills?.length ? m.skills.map((s: any) => `${s.skill} (${fa(s.level)})`).join("، ") : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </Card>

      {modal === "invite" && <InviteModal appId={id} users={users} onClose={() => setModal("")} onDone={() => { setModal(""); load(); }} />}
      {modal === "decide" && <DecideModal id={id} onClose={() => setModal("")} onDone={() => { setModal(""); load(); }} />}
    </div>
  );
}

function InviteModal({ appId, users, onClose, onDone }: any) {
  const [q, setQ] = useState("");
  const [list, setList] = useState(users);
  useEffect(() => {
    const t = setTimeout(() => api("/users?q=" + q).then((d) => setList(d.items)).catch(() => {}), 300);
    return () => clearTimeout(t);
  }, [q]);
  return (
    <Modal title="دعوت عضو به تیم" onClose={onClose}>
      <Field label="جست‌وجو بر اساس نام یا ایمیل"><input autoFocus value={q} onChange={(e: any) => setQ(e.target.value)} /></Field>
      <div className="tbl-wrap"><table className="tbl">
        <thead><tr><th>نام</th><th>نوع</th><th></th></tr></thead>
        <tbody>{list.map((u: any) => (
          <tr key={u.id}><td>{u.full_name}</td><td>{label(u.user_type)}</td>
            <td><button className="btn sm primary" onClick={async () => { await api(`/applications/${appId}/members`, { method: "POST", body: { user_email: u.email } }); onDone(); }}>دعوت</button></td>
          </tr>
        ))}</tbody>
      </table></div>
    </Modal>
  );
}

function DecideModal({ id, onClose, onDone }: any) {
  const [decision, setDecision] = useState("accept");
  const [reason, setReason] = useState("");
  const [err, setErr] = useState("");
  const go = async () => {
    setErr("");
    try { await api("/applications/" + id + "/decisions", { method: "POST", body: { decision, reason } }); onDone(); }
    catch (e: any) { setErr(e.message); }
  };
  return (
    <Modal title="ثبت تصمیم نهایی (انسانی و قابل حسابرسی)" onClose={onClose}>
      {err && <Alert kind="error">{err}</Alert>}
      <Field label="تصمیم">
        <select value={decision} onChange={(e: any) => setDecision(e.target.value)}>
          <option value="accept">پذیرش همکاری</option>
          <option value="reject">عدم پذیرش</option>
        </select></Field>
      <Field label="دلیل (الزامی — در حسابرسی ثبت می‌شود)"><textarea value={reason} onChange={(e: any) => setReason(e.target.value)} /></Field>
      <button className="btn primary" disabled={reason.trim().length < 5} onClick={go}>ثبت تصمیم</button>
    </Modal>
  );
}
