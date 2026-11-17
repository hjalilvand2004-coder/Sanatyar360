// داشبورد نقش‌محور
import React, { useEffect, useState } from "react";
import { api, fa, jalali, statusBadge, label } from "../api";
import { Card, Kpi, Empty } from "../ui";
import { useApp } from "../App";

export default function Dashboard() {
  const { me, nav, userType } = useApp();
  const [problems, setProblems] = useState<any[]>([]);
  const [apps, setApps] = useState<any[]>([]);
  const [projects, setProjects] = useState<any[]>([]);

  useEffect(() => {
    api("/problems?limit=200").then((d) => setProblems(d.items)).catch(() => {});
    api("/applications").then((d) => setApps(d.items)).catch(() => {});
    api("/collaborations").then((d) => setProjects(d.items)).catch(() => {});
  }, []);

  const roles = new Set(me.memberships.map((m: any) => m.role));
  const isStaff = [...roles].some((r: string) => ["cio_manager", "cio_expert", "comm_expert", "university_admin", "sys_admin", "policy_maker"].includes(r));
  const isIndustry = roles.has("industry_rep") || roles.has("industry_manager");
  const myApps = apps.filter((a) => ["submitted", "under_review", "shortlisted", "accepted"].includes(a.status));
  const activeProjects = projects.filter((p) => p.status === "active");
  const reviewPending = problems.filter((p) => p.status === "submitted" || p.status === "under_review");
  const published = problems.filter((p) => p.status === "published");

  const quick = [];
  if (isStaff) quick.push({ t: "مسائل در صف بررسی", n: reviewPending.length, to: "/review", d: "نیازمند تصمیم انتشار یا اصلاح" });
  if (isStaff) quick.push({ t: "مسائل منتشرشده", n: published.length, to: "/problems", d: "فراخوان‌های باز صنعت" });
  if (isIndustry) quick.push({ t: "مسائل سازمان من", n: problems.filter((p) => me.memberships.some((m: any) => m.organization_id === p.owner.id)).length, to: "/my-problems", d: "مدیریت فراخوان‌ها و متقاضیان" });
  if (userType === "student" || userType === "professor") quick.push({ t: "درخواست‌های من", n: myApps.length, to: "/applications", d: "در جریان بررسی یا پذیرش" });
  if (userType === "student" || userType === "professor") quick.push({ t: "پیشنهادهای سامانه", to: "/recommendations", d: "مسائل متناسب با مهارت‌های شما" });
  quick.push({ t: "همکاری‌های من", n: projects.length, to: "/collaborations", d: `فعال: ${fa(activeProjects.length)}` });

  return (
    <div>
      <div className="alert info">
        چرخه سامانه: ثبت مسئله ← بررسی و انتشار ← شناسایی ظرفیت ← درخواست همکاری ← توافق و تیم ← پیگیری ← ثبت دستاورد.
        پیشنهادهای هوشمند فقط «پیشنهاد سامانه» هستند؛ تصمیم نهایی با کارشناس و طرف‌های همکاری است.
      </div>
      <div className="grid cols-4">
        <Kpi val={fa(problems.length)} lbl="مسائل ثبت‌شده در سامانه" />
        <Kpi val={fa(published.length)} lbl="فراخوان منتشرشده" color="#16a34a" />
        <Kpi val={fa(myApps.length)} lbl="درخواست‌های من در جریان" color="#d97706" />
        <Kpi val={fa(activeProjects.length)} lbl="همکاری فعال من" color="#0d9488" />
      </div>
      <Card title="دسترسی سریع">
        <div className="grid cols-3">
          {quick.map((q, i) => (
            <div key={i} className="card" style={{ margin: 0, cursor: "pointer" }} onClick={() => nav(q.to)}>
              <b style={{ color: "var(--primary-dark)" }}>{q.t}</b>
              <div className="muted">{q.d}</div>
              {q.n !== undefined && <div style={{ fontSize: 22, fontWeight: 700, color: "var(--teal)" }}>{fa(q.n)}</div>}
            </div>
          ))}
        </div>
      </Card>
      <Card title="آخرین مسائل بازار صنعت" extra={<button className="btn sm" onClick={() => nav("/problems")}>مشاهده همه</button>}>
        {problems.length === 0 ? <Empty /> : (
          <div className="tbl-wrap"><table className="tbl">
            <thead><tr><th>عنوان</th><th>سازمان</th><th>وضعیت</th><th>محرمانگی</th><th>مهلت</th></tr></thead>
            <tbody>
              {problems.slice(0, 6).map((p) => (
                <tr key={p.id} style={{ cursor: "pointer" }} onClick={() => nav("/problem/" + p.id)}>
                  <td><b>{p.title}</b><div className="muted">{p.required_skills.slice(0, 3).join(" • ")}</div></td>
                  <td>{p.owner.name}</td>
                  <td>{statusBadge(p.status)}</td>
                  <td>{statusBadge(p.confidentiality_level)}</td>
                  <td>{jalali(p.application_deadline)}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </Card>
      {projects.length > 0 && (
        <Card title="همکاری‌های در جریان" extra={<button className="btn sm" onClick={() => nav("/collaborations")}>مشاهده همه</button>}>
          <div className="tbl-wrap"><table className="tbl">
            <thead><tr><th>کد</th><th>عنوان</th><th>وضعیت</th></tr></thead>
            <tbody>
              {projects.slice(0, 5).map((p) => (
                <tr key={p.id} style={{ cursor: "pointer" }} onClick={() => nav("/collaboration/" + p.id)}>
                  <td><code>{p.code}</code></td>
                  <td>{p.title}</td>
                  <td>{statusBadge(p.status)}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        </Card>
      )}
    </div>
  );
}
