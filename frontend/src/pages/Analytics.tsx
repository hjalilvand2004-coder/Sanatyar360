// تحلیل‌ها: خلاصه شاخص‌ها، تقاضای مهارت، شبکه همکاری، کیفیت داده
import React, { useEffect, useState } from "react";
import { api, fa, jalali, label } from "../api";
import { Card, Empty, Alert, BarChart, LineChart, NetworkGraph } from "../ui";

export default function Analytics() {
  const [summary, setSummary] = useState<any>(null);
  const [outcomes, setOutcomes] = useState<any>(null);
  const [demand, setDemand] = useState<any>(null);
  const [network, setNetwork] = useState<any>(null);
  const [quality, setQuality] = useState<any>(null);
  const [maharat, setMaharat] = useState<any>(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    Promise.all([
      api("/analytics/summary").then(setSummary).catch(() => {}),
      api("/analytics/skill-demand?months=6").then(setDemand).catch(() => {}),
      api("/analytics/collaboration-network").then(setNetwork).catch(() => {}),
      api("/analytics/quality").then(setQuality).catch(() => {}),
      api("/analytics/outcomes").then(setOutcomes).catch(() => {}),
      api("/maharat/status").then(setMaharat).catch(() => {}),
    ]);
  }, []);

  if (err) return <Alert kind="error">{err}</Alert>;

  return (
    <div>
      <Alert kind="info">
        تحلیل‌های تجمیعی و ناشناس برای سیاست‌گذار و مدیر دانشگاه. افزایش تعداد آگهی لزوماً به معنای افزایش کل تقاضا نیست —
        منبع، تاریخ و محدودیت پوشش داده در هر نمودار نمایش داده می‌شود (AC-10).
      </Alert>
      {outcomes && (
        <Card title="🎯 شاخص‌های نتیجه‌محور — ارزش خروجی، نه تعداد ورودی">
          <Alert kind="ok"><b>{outcomes.headline}</b> — مقدار جاری: <b>{fa(outcomes.solved_with_measured_outcome)}</b></Alert>
          <div className="grid cols-4">
            <div className="kpi"><div className="val">{outcomes.time_to_team_days_median != null ? fa(outcomes.time_to_team_days_median) : "—"}</div><div className="lbl">میانهٔ روز از ثبت مسئله تا تیم مناسب</div></div>
            <div className="kpi"><div className="val">{outcomes.conversion?.problem_to_collaboration_pct != null ? fa(outcomes.conversion.problem_to_collaboration_pct) + "٪" : "—"}</div><div className="lbl">تبدیل مسئله به همکاری</div></div>
            <div className="kpi"><div className="val">{outcomes.conversion?.problem_to_contract_pct != null ? fa(outcomes.conversion.problem_to_contract_pct) + "٪" : "—"}</div><div className="lbl">تبدیل مسئله به قرارداد</div></div>
            <div className="kpi"><div className="val">{outcomes.on_time_delivery_pct != null ? fa(outcomes.on_time_delivery_pct) + "٪" : "—"}</div><div className="lbl">تحویل به‌موقع و پذیرش خروجی</div></div>
            <div className="kpi"><div className="val">{outcomes.repeat_collaboration_pct != null ? fa(outcomes.repeat_collaboration_pct) + "٪" : "—"}</div><div className="lbl">نرخ همکاری مجدد شرکت‌ها</div></div>
            <div className="kpi"><div className="val">{fa(outcomes.solved_with_measured_outcome)}</div><div className="lbl">مسئله حل‌شده با نتیجهٔ قابل‌اندازه‌گیری و تأییدشده</div></div>
          </div>
          <p style={{ fontSize: 12, opacity: 0.65, marginTop: 8 }}>{outcomes.note} — پایهٔ سنجش «پایلوت» با تصمیم صنعت است؛ یعنی همان مسیری که ریسک را کم و اعتماد را زیاد می‌کند.</p>
        </Card>
      )}
      {summary && (
        <Card title="شاخص‌های کلیدی سامانه">
          <div className="grid cols-4">
            <div className="kpi"><div className="val">{fa(summary.problems?.total)}</div><div className="lbl">مسئله ثبت‌شده</div></div>
            <div className="kpi"><div className="val">{summary.problems?.conversion_rate !== null && summary.problems?.conversion_rate !== undefined ? Math.round(summary.problems.conversion_rate * 100).toLocaleString("fa-IR") + "٪" : "—"}</div><div className="lbl">نرخ تبدیل مسئله به همکاری</div></div>
            <div className="kpi"><div className="val">{fa(summary.avg_days_problem_to_collaboration)}</div><div className="lbl">میانگین روز تا شکل‌گیری همکاری</div></div>
            <div className="kpi"><div className="val">{summary.collaborations?.completion_rate != null ? Math.round(summary.collaborations.completion_rate * 100).toLocaleString("fa-IR") + "٪" : "—"}</div><div className="lbl">نرخ تکمیل همکاری</div></div>
            <div className="kpi"><div className="val">{fa(summary.collaborations?.repeat_industry_partners)}</div><div className="lbl">صنایع با همکاری مجدد</div></div>
            <div className="kpi"><div className="val">{fa(summary.applications?.total)}</div><div className="lbl">درخواست همکاری</div></div>
            <div className="kpi"><div className="val">{fa(summary.commercialization_cases)}</div><div className="lbl">فرصت تجاری‌سازی ثبت‌شده</div></div>
          </div>
        </Card>
      )}
      {maharat && (
        <Card title="یکپارچگی با مهارت‌یار۳۶۰ (اکوسیستم دانشجویار۳۶۰)">
          <div className="grid cols-4">
            <div className="kpi"><div className="val">{maharat.mode === "live" ? "زنده" : maharat.mode === "disabled" ? "غیرفعال" : "آفلاین"}</div><div className="lbl">وضعیت ارتباط</div></div>
            <div className="kpi"><div className="val">{fa(maharat.linked_users)}</div><div className="lbl">کاربر با پروفایل مهارتی پیوند خورده</div></div>
            <div className="kpi"><div className="val">{maharat.skills_count ? fa(maharat.skills_count) : "—"}</div><div className="lbl">مهارت در واژه‌نامه مشترک</div></div>
            <div className="kpi"><div className="val">{maharat.careers_count ? fa(maharat.careers_count) : "—"}</div><div className="lbl">شغل مرجع برای تطبیق شغلی</div></div>
          </div>
          <p style={{ fontSize: 12, opacity: 0.65, marginTop: 8 }}>
            سطوح مهارتی تأییدشده از مهارت‌یار۳۶۰ در موتور تطبیق صنعت‌یار به‌عنوان شواهد معتبر لحاظ می‌شود
            و پنل «شکاف مهارتی» هر مسئله بر مبنای همان واژه‌نامه مشترک ساخته می‌شود.
          </p>
        </Card>
      )}
      {demand && (
        <div className="grid cols-2">
          <Card title="روند تقاضای مهارت در منابع بازار (۶ ماه اخیر)">
            <LineChart data={demand.market_by_month.map((x: any) => ({ label: x.month.slice(2), value: x.demand }))} />
            <div className="chart-legend">
              <span><span className="sw" style={{ background: "#4f46e5" }} />تعداد مشاهدات ماهانه</span>
              <span>منابع: {demand.sources.join("، ")}</span>
            </div>
            <div className="muted" style={{ marginTop: 6 }}>آخرین به‌روزرسانی: {jalali(demand.generated_at, true)} | {demand.coverage_note}</div>
          </Card>
          <Card title="مهارت‌های پرتکرار در مسائل صنعتی ثبت‌شده">
            <BarChart data={demand.problems_demand.slice(0, 10).map((x: any) => ({ label: x.skill, value: x.count }))} unit=" مسئله" />
            <div className="muted">مبنای داده: مهارت‌های الزامی مسائل همین سامانه</div>
          </Card>
        </div>
      )}
      {demand && (
        <div className="grid cols-2">
          <Card title="مهارت‌های نوظهور (رشد در نیم‌بازه دوم)">
            {demand.emerging_skills.length === 0 ? <Empty /> : (
              <BarChart data={demand.emerging_skills.slice(0, 6).map((x: any) => ({ label: x.skill, value: x.growth }))} unit="×" />
            )}
            <div className="muted">مقایسه فراوانی دو نیم‌بازه؛ حداقل نمونه: {fa(demand.min_sample_threshold)}</div>
          </Card>
          <Card title="کیفیت و محدودیت داده">
            <dl className="detail-grid">
              <dt>مسائل دارای معیار پذیرش</dt><dd>{quality?.problems_with_acceptance_criteria_pct != null ? Math.round(quality.problems_with_acceptance_criteria_pct * 100).toLocaleString("fa-IR") + "٪" : "—"}</dd>
              <dt>رکورد مهارت تکراری</dt><dd>{fa(quality?.duplicate_skill_rows)}</dd>
              <dt>مشاهدات بازار</dt><dd>{fa(quality?.market_observations_total)}</dd>
              <dt>تازگی داده بازار</dt><dd>{jalali(quality?.market_data_freshness, true)}</dd>
            </dl>
          </Card>
        </div>
      )}
      {network && (
        <Card title="شبکه همکاری دانشگاه و صنعت">
          <NetworkGraph nodes={network.nodes} edges={network.edges} />
          <div className="grid cols-4" style={{ marginTop: 12 }}>
            <div className="kpi"><div className="val">{fa(network.stats?.active_partners)}</div><div className="lbl">شرکای صنعتی فعال</div></div>
            <div className="kpi"><div className="val">{fa(network.stats?.universities)}</div><div className="lbl">دانشگاه‌ها</div></div>
            <div className="kpi"><div className="val">{fa(network.stats?.total_projects)}</div><div className="lbl">پروژه همکاری</div></div>
            <div className="kpi"><div className="val">{fa(network.stats?.repeated_collaborations)}</div><div className="lbl">همکاری تکرارشونده</div></div>
          </div>
          <Alert kind="info" >
            هر یال به همکاری واقعی قابل ردیابی است (کد پروژه در API). مرکزیت در شبکه معیار قطعی کیفیت علمی یا عملکرد فردی نیست و نباید به‌تنهایی برای رتبه‌بندی افراد استفاده شود.
          </Alert>
        </Card>
      )}
    </div>
  );
}
