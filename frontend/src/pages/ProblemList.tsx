// بازار مسائل + مسائل سازمان من (مود route)
import React, { useEffect, useState } from "react";
import { api, jalali, statusBadge, money, label } from "../api";
import { Card, Empty, Alert } from "../ui";
import { useApp } from "../App";

export default function ProblemList({ route }: any) {
  const { me, nav, userType } = useApp();
  const mine = route === "/my-problems";
  const [items, setItems] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [sector, setSector] = useState("");
  const [work, setWork] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const p = new URLSearchParams({ limit: "100" });
    if (q) p.set("q", q);
    if (sector) p.set("sector", sector);
    if (work) p.set("work_mode", work);
    if (status) p.set("status", status);
    if (mine) p.set("mine", "1");
    api("/problems?" + p.toString()).then((d) => setItems(d.items)).catch(() => setItems([])).finally(() => setLoading(false));
  }, [q, sector, work, status, mine]);

  const isIndustry = me.memberships.some((m: any) => ["industry_rep", "industry_manager"].includes(m.role));
  const canSeeReview = me.memberships.some((m: any) => ["cio_manager", "cio_expert"].includes(m.role));

  return (
    <div>
      {mine && isIndustry && (
        <div className="btn-row" style={{ marginBottom: 14 }}>
          <button className="btn primary" onClick={() => nav("/problems/new")}>＋ ثبت مسئله جدید</button>
          <span className="muted">مسئله با وضعیت پیش‌نویس/نیازمند اصلاح قابل ویرایش است؛ پس از ارسال وارد صف بررسی می‌شود.</span>
        </div>
      )}
      <Card>
        <div className="filters">
          <div className="field"><label>جست‌وجو</label>
            <input placeholder="عنوان یا خلاصه…" value={q} onChange={(e: any) => setQ(e.target.value)} /></div>
          <div className="field compact"><label>حوزه صنعت</label>
            <select value={sector} onChange={(e: any) => setSector(e.target.value)}>
              <option value="">همه</option><option value="MAN-01">ماشین‌سازی</option><option value="MET-02">فلزات</option>
            </select></div>
          <div className="field compact"><label>نوع اجرا</label>
            <select value={work} onChange={(e: any) => setWork(e.target.value)}>
              <option value="">همه</option><option value="onsite">حضوری</option><option value="remote">دورکاری</option><option value="hybrid">ترکیبی</option>
            </select></div>
          {isIndustry && (
            <div className="field compact"><label>وضعیت</label>
              <select value={status} onChange={(e: any) => setStatus(e.target.value)}>
                <option value="">همه</option>
                {["draft", "submitted", "under_review", "needs_revision", "published", "applications_closed", "converted_to_project"].map((s) => (
                  <option key={s} value={s}>{label(s)}</option>
                ))}
              </select></div>
          )}
        </div>
        {loading ? <Empty text="در حال بارگذاری…" /> : items.length === 0 ? <Empty /> : (
          <div className="tbl-wrap"><table className="tbl">
            <thead><tr>
              <th>عنوان مسئله</th><th>سازمان</th><th>وضعیت</th><th>سطح دسترسی</th><th>بودجه</th><th>مهلت درخواست</th><th></th>
            </tr></thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.id}>
                  <td><a href={"#/problem/" + p.id}><b>{p.title}</b></a>
                    <div className="chips" style={{ marginTop: 5 }}>{p.required_skills.slice(0, 4).map((s: string) => <span key={s} className="chip">{s}</span>)}</div></td>
                  <td>{p.owner.name}</td>
                  <td>{statusBadge(p.status)}</td>
                  <td>{statusBadge(p.confidentiality_level)}</td>
                  <td>{money(p.budget_min, p.currency) && money(p.budget_min, p.currency) + " تا " + (money(p.budget_max, p.currency) || "")}</td>
                  <td>{jalali(p.application_deadline)}</td>
                  <td><button className="btn sm" onClick={() => nav("/problem/" + p.id)}>مشاهده</button></td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </Card>
      {!mine && (
        <Alert kind="info">
          مسائل با سطح دسترسی «محرمانه» فقط برای سازمان مالک و دفتر ارتباط با صنعت نمایش داده می‌شود.
          در مسائل «شرکت‌کنندگان منتخب»، جزئیات فقط برای متقاضیان مجاز باز می‌شود.
        </Alert>
      )}
    </div>
  );
}
