// اعلان‌ها، حریم خصوصی و رضایت‌ها، حسابرسی
import React, { useEffect, useState } from "react";
import { api, jalali, label, fa } from "../api";
import { Card, Empty, Alert } from "../ui";
import { useApp } from "../App";

export function Notifications() {
  const { nav, refreshNotifs } = useApp();
  const [items, setItems] = useState<any[]>([]);
  const load = () => api("/notifications").then((d) => setItems(d.items)).catch(() => {});
  useEffect(load, []);
  return (
    <Card title="مرکز اعلان‌ها" extra={<button className="btn sm" onClick={async () => { await api("/notifications/read-all", { method: "POST" }); load(); refreshNotifs(); }}>خواندن همه</button>}>
      {items.length === 0 ? <Empty text="اعلانی ندارید" /> : items.map((n) => (
        <div key={n.id} style={{ borderBottom: "1px solid var(--border)", paddingBottom: 10, marginBottom: 10, opacity: n.is_read ? 0.65 : 1 }}>
          <b>{n.is_read ? "" : "🔵 "}{n.title}</b>
          <div className="muted">{n.body}</div>
          <div className="muted">{jalali(n.created_at, true)} {n.link && <a href={"#" + n.link}>مشاهده</a>}</div>
        </div>
      ))}
    </Card>
  );
}

export function Privacy() {
  const { me, notify } = useApp();
  const [skills, setSkills] = useState<any[]>([]);
  const [consents, setConsents] = useState<any[]>(me.consents || []);
  const [ns, setNs] = useState({ name: "", level: 3, evidence_note: "" });

  const loadSkills = () => api("/me/skills").then((d) => setSkills(d.items)).catch(() => {});
  useEffect(loadSkills, []);

  const consentGranted = (t: string) => {
    const c = consents.find((x) => x.consent_type === t);
    return c ? (c.granted && !c.revoked) : false;
  };
  const toggle = async (t: string) => {
    await api("/me/consents", { method: "POST", body: { consent_type: t, granted: !consentGranted(t) } });
    const d = await api("/auth/me");
    setConsents(d.consents);
    notify("وضعیت رضایت ثبت و در حسابرسی لاگ شد");
  };

  return (
    <div>
      <Card title="رضایت اشتراک اطلاعات با صنعت">
        <Alert kind="info">بدون رضایت شما، صنعت فقط پروفایل حداقلی (نام، نقش، توضیح تناسب) می‌بیند — AC-05.</Alert>
        <label style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 10 }}>
          <input type="checkbox" checked={consentGranted("profile_share_industry")} onChange={() => toggle("profile_share_industry")} />
          <span><b>اشتراک پروفایل کامل با سازمان‌های صنعتی مالک مسئله و دفتر ارتباط با صنعت</b><br />
            <span className="muted">شامل ایمیل، گروه، مقطع و سوابق؛ قابل لغو در هر زمان</span></span>
        </label>
        <label style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <input type="checkbox" checked={consentGranted("data_usage")} onChange={() => toggle("data_usage")} />
          <span><b>استفاده از مهارت‌ها و ترجیحات در موتور تطبیق و پیشنهاددهی</b><br />
            <span className="muted">برای نمایش پیشنهادهای شخصی</span></span>
        </label>
      </Card>
      <Card title="مهارت‌های من (شواهد و سطح)">
        <div className="tbl-wrap"><table className="tbl">
          <thead><tr><th>مهارت</th><th>سطح (۱-۵)</th><th>منشأ</th><th>شواهد</th></tr></thead>
          <tbody>{skills.map((s, i) => (
            <tr key={i}><td><b>{s.skill}</b></td><td>{fa(s.level)}</td><td>{label(s.source)}</td><td className="muted">{s.evidence_note || "—"}</td></tr>
          ))}</tbody>
        </table></div>
        <hr className="divider" />
        <div className="grid cols-4">
          <div className="field"><label>مهارت جدید</label><input value={ns.name} onChange={(e: any) => setNs({ ...ns, name: e.target.value })} /></div>
          <div className="field"><label>سطح</label>
            <select value={ns.level} onChange={(e: any) => setNs({ ...ns, level: +e.target.value })}>
              {[1, 2, 3, 4, 5].map((x) => <option key={x} value={x}>{x.toLocaleString("fa-IR")}</option>)}
            </select></div>
          <div className="field"><label>شواهد (اختیاری)</label><input value={ns.evidence_note} onChange={(e: any) => setNs({ ...ns, evidence_note: e.target.value })} /></div>
          <div className="field"><label>&nbsp;</label>
            <button className="btn primary" disabled={!ns.name} onClick={async () => { await api("/me/skills", { method: "POST", body: ns }); setNs({ name: "", level: 3, evidence_note: "" }); loadSkills(); notify("مهارت ثبت شد"); }}>افزودن مهارت</button></div>
        </div>
      </Card>
    </div>
  );
}

export function Audit() {
  const [items, setItems] = useState<any[]>([]);
  const [action, setAction] = useState("");
  useEffect(() => {
    api("/audit-logs" + (action ? "?action=" + action : "")).then((d) => setItems(d.items)).catch(() => {});
  }, [action]);
  return (
    <div>
      <Alert kind="info">تمام عملیات حساس (ورود، تصمیم‌ها، انتشار، تغییر وضعیت، رضایت‌ها) با عامل، زمان و موضوع ثبت می‌شود — AC-15. دسترسی مدیر فنی اضطراری و قابل حسابرسی است.</Alert>
      <Card extra={
        <select className="btn" value={action} onChange={(e: any) => setAction(e.target.value)}>
          <option value="">همه اقدامات</option>
          {["login", "login_failed", "problem_created", "problem_submitted", "problem_review_", "problem_published",
            "application_submitted", "application_accept", "application_reject", "match_run_executed",
            "collaboration_created", "project_status_", "deliverable_accept", "consent_changed", "verification_"].map((a) => (
            <option key={a} value={a}>{a}</option>
          ))}
        </select>}>
        {items.length === 0 ? <Empty /> : (
          <div className="tbl-wrap"><table className="tbl">
            <thead><tr><th>زمان</th><th>عامل</th><th>اقدام</th><th>موضوع</th><th>جزئیات</th><th>IP</th></tr></thead>
            <tbody>{items.map((a) => (
              <tr key={a.id}>
                <td style={{ whiteSpace: "nowrap" }}>{jalali(a.created_at, true)}</td>
                <td>{a.actor}</td>
                <td><code>{a.action}</code></td>
                <td>{label(a.entity_type)} <span className="muted">({a.entity_id?.slice(0, 8)}…)</span></td>
                <td className="muted" style={{ maxWidth: 260 }}>{a.detail ? JSON.stringify(a.detail).slice(0, 120) : "—"}</td>
                <td>{a.ip || "—"}</td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
    </div>
  );
}
