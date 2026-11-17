// صف بررسی دفتر ارتباط با صنعت: سازمان‌های در انتظار احراز + مسائل در انتظار تصمیم
import React, { useEffect, useState } from "react";
import { api, jalali, statusBadge, label } from "../api";
import { Card, Empty, Alert, Modal, Field } from "../ui";
import { useApp } from "../App";

export default function ReviewQueue() {
  const { nav, notify } = useApp();
  const [orgs, setOrgs] = useState<any[]>([]);
  const [problems, setProblems] = useState<any[]>([]);
  const [reviewP, setReviewP] = useState<any>(null);

  const load = () => {
    api("/organizations?org_type=industry").then((d) => setOrgs(d.items)).catch(() => {});
    api("/problems?limit=100").then((d) => setProblems(d.items)).catch(() => {});
  };
  useEffect(load, []);

  const pendingOrgs = orgs.filter((o) => o.status === "pending");
  const reviewProblems = problems.filter((p) => ["submitted", "under_review", "needs_revision"].includes(p.status));

  const verify = async (orgId: string, decision: string) => {
    const note = decision === "rejected" ? prompt("دلیل رد احراز:") || "مستندات ناقص" : "مستندات بررسی و تأیید شد";
    try { await api(`/organizations/${orgId}/verification`, { method: "POST", body: { decision, review_note: note } }); notify("وضعیت احراز ثبت شد"); load(); }
    catch (e: any) { alert(e.message); }
  };

  return (
    <div>
      <Alert kind="info">
        جریان کار دفتر: احراز سازمان‌ها ← بررسی مسئله (کارشناس حوزه تخصصی) ← انتشار (مدیر دفتر) ← پیگیری هماهنگی تطبیق و انتخاب.
      </Alert>
      <Card title={`سازمان‌های صنعتی در انتظار احراز (${pendingOrgs.length.toLocaleString("fa-IR")})`}>
        {pendingOrgs.length === 0 ? <Empty text="صف خالی است" /> : (
          <div className="tbl-wrap"><table className="tbl">
            <thead><tr><th>سازمان</th><th>حوزه</th><th>شهر</th><th>ثبت‌کننده</th><th></th></tr></thead>
            <tbody>{pendingOrgs.map((o) => (
              <tr key={o.id}>
                <td><b>{o.name}</b></td><td>{o.industry_sector || "—"}</td><td>{o.city || "—"}</td>
                <td><button className="btn sm ok" onClick={() => verify(o.id, "approved")}>تأیید احراز</button></td>
                <td><button className="btn sm danger" onClick={() => verify(o.id, "rejected")}>رد</button></td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
      <Card title={`مسائل نیازمند تصمیم (${reviewProblems.length.toLocaleString("fa-IR")})`}>
        {reviewProblems.length === 0 ? <Empty text="صف بررسی خالی است" /> : (
          <div className="tbl-wrap"><table className="tbl">
            <thead><tr><th>عنوان</th><th>سازمان</th><th>وضعیت</th><th>محرومانگی</th><th></th></tr></thead>
            <tbody>{reviewProblems.map((p) => (
              <tr key={p.id}>
                <td><b>{p.title}</b><div className="muted">{p.summary.slice(0, 80)}…</div></td>
                <td>{p.owner.name} {statusBadge(p.owner.status)}</td>
                <td>{statusBadge(p.status)}</td>
                <td>{statusBadge(p.confidentiality_level)}</td>
                <td><button className="btn sm primary" onClick={() => nav("/problem/" + p.id)}>بررسی و تصمیم</button></td>
              </tr>
            ))}</tbody>
          </table></div>
        )}
      </Card>
    </div>
  );
}
