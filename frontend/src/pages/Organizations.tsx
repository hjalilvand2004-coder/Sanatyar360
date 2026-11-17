// پایگاه سازمان‌ها: فهرست، ثبت سازمان جدید، مشاهده وضعیت احراز
import React, { useEffect, useState } from "react";
import { api, statusBadge, jalali } from "../api";
import { Card, Empty, Alert, Modal, Field } from "../ui";
import { useApp } from "../App";

export default function Organizations() {
  const { me, notify } = useApp();
  const [items, setItems] = useState<any[]>([]);
  const [modal, setModal] = useState(false);
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [detail, setDetail] = useState<any>(null);

  const load = () => {
    const p = new URLSearchParams();
    if (q) p.set("q", q);
    if (type) p.set("org_type", type);
    api("/organizations?" + p.toString()).then((d) => setItems(d.items)).catch(() => {});
  };
  useEffect(load, [q, type]);

  const openDetail = (id: string) => api("/organizations/" + id).then(setDetail).catch(() => {});

  return (
    <div>
      <Alert kind="info">
        معتبر بودن هویت سازمان به معنای تأیید کیفیت همه مسائل یا تضمین پرداخت آن نیست.
      </Alert>
      <Card extra={
        <div className="btn-row">
          <input className="btn" style={{ width: 220 }} placeholder="جست‌وجوی نام…" value={q} onChange={(e: any) => setQ(e.target.value)} />
          <select className="btn" value={type} onChange={(e: any) => setType(e.target.value)}>
            <option value="">همه انواع</option><option value="industry">صنعت</option><option value="university">دانشگاه</option>
          </select>
          <button className="btn primary" onClick={() => setModal(true)}>＋ ثبت سازمان جدید</button>
        </div>}>
        {items.length === 0 ? <Empty /> : (
          <div className="tbl-wrap"><table className="tbl">
            <thead><tr><th>نام</th><th>نوع</th><th>حوزه صنعت</th><th>شهر</th><th>وضعیت احراز</th><th></th></tr></thead>
            <tbody>{items.map((o) => (
              <tr key={o.id}>
                <td><b>{o.name}</b></td>
                <td><span className={"badge " + (o.org_type === "industry" ? "teal" : "blue")}>{o.org_type === "industry" ? "سازمان صنعتی" : "دانشگاه"}</span></td>
                <td>{o.industry_sector || "—"}</td><td>{o.city || "—"}</td><td>{statusBadge(o.status)}</td>
                <td><button className="btn sm" onClick={() => openDetail(o.id)}>جزئیات</button></td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>

      {modal && <NewOrgModal onClose={() => setModal(false)} onDone={() => { setModal(false); notify("سازمان ثبت شد — درخواست احراز برای دفتر ارسال گردید"); load(); }} />}
      {detail && (
        <Modal title={detail.name} onClose={() => setDetail(null)}>
          <dl className="detail-grid">
            <dt>نوع</dt><dd>{detail.org_type === "industry" ? "سازمان صنعتی" : "دانشگاه"}</dd>
            <dt>شناسه قانونی</dt><dd>{detail.legal_id || "—"}</dd>
            <dt>حوزه / اندازه</dt><dd>{detail.industry_sector || "—"} / {detail.size || "—"}</dd>
            <dt>وب‌سایت</dt><dd>{detail.website || "—"}</dd>
            <dt>وضعیت احراز</dt><dd>{statusBadge(detail.status)}</dd>
            <dt>توضیح</dt><dd>{detail.description || "—"}</dd>
            {detail.restriction_note && <><dt>محدودیت همکاری</dt><dd style={{ color: "var(--danger)" }}>{detail.restriction_note}</dd></>}
          </dl>
          {detail.members?.length > 0 && (
            <div><h3>اعضای سازمان</h3><div className="chips">
              {detail.members.map((m: any, i: number) => <span key={i} className="chip">{m.user.full_name} — {m.role_label}</span>)}
            </div></div>
          )}
          {detail.verifications?.length > 0 && (
            <div><h3>سوابق احراز</h3>{detail.verifications.map((v: any, i: number) => (
              <div key={i} className="muted">{statusBadge(v.status)} — {v.documents_note || "—"} {v.review_note ? "| " + v.review_note : ""} ({jalali(v.created_at)})</div>
            ))}</div>
          )}
          {detail.status === "pending" && me.memberships.some((m: any) => ["industry_rep", "industry_manager"].includes(m.role) && m.organization_id === detail.id) && (
            <button className="btn primary" onClick={async () => { await api(`/organizations/${detail.id}/verification-requests`, { method: "POST", body: { documents_note: "درخواست مجدد احراز" } }); setDetail(null); notify("درخواست احراز ارسال شد"); }}>ارسال درخواست احراز</button>
          )}
        </Modal>
      )}
    </div>
  );
}

const NewOrgModal = ({ onClose, onDone }: any) => {
  const [f, setF] = useState({ name: "", org_type: "industry", legal_id: "", industry_sector: "", size: "", city: "", website: "", description: "" });
  const [err, setErr] = useState("");
  const set = (k: string, v: any) => setF({ ...f, [k]: v });
  return (
    <Modal title="ثبت سازمان جدید" onClose={onClose}>
      {err && <Alert kind="error">{err}</Alert>}
      <Field label="نام سازمان"><input value={f.name} onChange={(e: any) => set("name", e.target.value)} /></Field>
      <div className="grid cols-2">
        <Field label="نوع"><select value={f.org_type} onChange={(e: any) => set("org_type", e.target.value)}>
          <option value="industry">سازمان صنعتی</option><option value="university">دانشگاه</option>
        </select></Field>
        <Field label="شناسه قانونی / ثبت"><input value={f.legal_id} onChange={(e: any) => set("legal_id", e.target.value)} /></Field>
        <Field label="حوزه صنعت"><input value={f.industry_sector} onChange={(e: any) => set("industry_sector", e.target.value)} /></Field>
        <Field label="اندازه"><input value={f.size} onChange={(e: any) => set("size", e.target.value)} placeholder="مثلاً ۵۰ تا ۲۰۰ نفر" /></Field>
        <Field label="شهر"><input value={f.city} onChange={(e: any) => set("city", e.target.value)} /></Field>
        <Field label="وب‌سایت"><input value={f.website} onChange={(e: any) => set("website", e.target.value)} /></Field>
      </div>
      <Field label="توضیح"><textarea value={f.description} onChange={(e: any) => set("description", e.target.value)} /></Field>
      <button className="btn primary" disabled={f.name.length < 3} onClick={async () => {
        setErr("");
        try { await api("/organizations", { method: "POST", body: f }); onDone(); }
        catch (e: any) { setErr(e.message); }
      }}>ثبت و ارسال برای احراز</button>
    </Modal>
  );
};
