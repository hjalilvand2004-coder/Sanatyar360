// مهارت‌یار۳۶۰ — پیوند پروفایل مهارتی تأییدشده از زیرسیستم اکوسیستم دانشجویار۳۶۰
import React, { useEffect, useState } from "react";
import { api, fa } from "../api";
import { Card, Empty, Alert, BarChart } from "../ui";
import { useApp } from "../App";

const levelColor = (lv: number) =>
  lv >= 80 ? "#22c55e" : lv >= 60 ? "#eab308" : lv > 0 ? "#f97316" : "#64748b";

export default function Maharat() {
  const { notify } = useApp();
  const [me, setMe] = useState<any>(null);
  const [status, setStatus] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [token, setToken] = useState("");
  const [showToken, setShowToken] = useState(false);

  const load = () => {
    api("/maharat/me").then(setMe).catch(() => {});
    api("/maharat/status").then(setStatus).catch(() => {});
  };
  useEffect(load, []);

  const link = async (body: any = {}) => {
    setBusy(true);
    try {
      const d = await api("/maharat/link", { method: "POST", body });
      notify("پیوند با مهارت‌یار۳۶۰ برقرار شد ✓");
      setMe(d); setShowToken(false); setToken("");
    } catch (ex: any) { notify(ex.message || "پیوند ناموفق بود"); }
    setBusy(false);
  };
  const unlink = async () => {
    setBusy(true);
    try { await api("/maharat/link", { method: "DELETE" }); setMe({ linked: false }); notify("پیوند قطع و داده‌ها حذف شد"); }
    catch (ex: any) { notify(ex.message || "خطا"); }
    setBusy(false);
  };
  const refresh = async () => {
    setBusy(true);
    try { const d = await api("/maharat/link/refresh", { method: "POST" }); setMe(d); notify(d.refreshed ? "از مهارت‌یار به‌روزرسانی شد ✓" : "به‌روزرسانی ممکن نشد — آخرین داده حفظ شد"); }
    catch (ex: any) { notify(ex.message || "خطا"); }
    setBusy(false);
  };

  return (
    <div>
      <Alert kind="info">
        <b>یکپارچگی اکوسیستم دانشجویار۳۶۰:</b> مهارت‌یار۳۶۰ پروفایل مهارتی شما را از مدارک، درس‌ها و پروژه‌ها
        می‌سازد؛ صنعت‌یار۳۶۰ همان سطوح تأییدشده را در تطبیق مسائل صنعتی، پیشنهادها و تحلیل شکاف مهارتی استفاده می‌کند.
        هیچ رمزی منتقل یا ذخیره نمی‌شود و قطع پیوند همه داده‌ها را حذف می‌کند.
      </Alert>

      {status && (
        <Card title="وضعیت ارتباط با مهارت‌یار۳۶۰">
          <div className="chips">
            <span className={"chip " + (status.mode === "live" ? "ok" : "")}>
              {status.mode === "live" ? "🟢 ارتباط زنده" : status.mode === "disabled" ? "غیرفعال" : "🟡 آفلاین — داده کش/نمونه"}
            </span>
            {status.app && <span className="chip">{status.app}</span>}
            {status.version && <span className="chip">نسخه {status.version}</span>}
            {status.skills_count ? <span className="chip">{fa(status.skills_count)} مهارت در واژه‌نامه</span> : null}
            {status.careers_count ? <span className="chip">{fa(status.careers_count)} شغل مرجع</span> : null}
            <span className="chip">{fa(status.linked_users)} کاربر پیوند خورده</span>
          </div>
        </Card>
      )}

      {!me || !me.linked ? (
        <Card title="پیوند پروفایل مهارتی">
          <p style={{ opacity: 0.85, lineHeight: 2 }}>
            با پیوند حساب مهارت‌یار۳۶۰، سطوح تأییدشده مهارت‌های شما به‌صورت خودکار در:
            موتور تطبیق مسائل، پیشنهادهای سامانه، و پنل «شکاف مهارتی» هر مسئله استفاده می‌شود.
          </p>
          <div className="btn-row" style={{ marginTop: 12 }}>
            <button className="btn primary" disabled={busy} onClick={() => link({})}>
              پیوند با حساب مهارت‌یار من (با ایمیل همین حساب)
            </button>
            <button className="btn" onClick={() => setShowToken(!showToken)}>با توکن مهارت‌یار</button>
          </div>
          {showToken && (
            <div style={{ marginTop: 10 }}>
              <input className="btn" dir="ltr" style={{ width: 420 }} placeholder="توکن دسترسی مهارت‌یار (access_token)"
                     value={token} onChange={(e: any) => setToken(e.target.value)} />
              <button className="btn primary" style={{ marginInlineStart: 8 }} disabled={busy || !token}
                      onClick={() => link({ token })}>برقراری پیوند</button>
              <p style={{ fontSize: 12, opacity: 0.6, marginTop: 6 }}>
                توکن فقط برای یک بار واکشی استفاده و هرگز ذخیره نمی‌شود.
              </p>
            </div>
          )}
        </Card>
      ) : (
        <>
          {me.is_sample && (
            <Alert kind="warn">
              این پروفایل <b>داده نمونه اکوسیستم</b> است (حالت آفلاین/نمونه). با اجرای مجدد به‌روزرسانی،
              در صورت دسترسی به مهارت‌یار۳۶۰ داده واقعی جایگزین می‌شود.
            </Alert>
          )}
          <Card title="پروفایل مهارتی تأییدشده" extra={
            <div className="btn-row">
              <button className="btn" disabled={busy} onClick={refresh}>به‌روزرسانی از مهارت‌یار</button>
              <button className="btn" disabled={busy} onClick={unlink}>قطع پیوند</button>
            </div>
          }>
            <div className="chips">
              {me.maharat_full_name && <span className="chip ok">{me.maharat_full_name}</span>}
              {me.major && <span className="chip">{me.major}</span>}
              {me.university_name && <span className="chip">{me.university_name}</span>}
              <span className="chip">{fa(me.skills_total)} مهارت ثبت‌شده</span>
              <span className="chip">{fa(me.verified_evidences)} مدرک تأییدشده</span>
              <span className="chip">منبع: {me.source === "self_token" ? "توکن شخصی" : me.source === "seed_sample" ? "داده نمونه" : "حساب سرویس"}</span>
            </div>
            {(!me.levels || me.levels.length === 0) ? <Empty /> : (
              <div style={{ marginTop: 14 }}>
                {(me.levels || []).map((lv: any) => (
                  <div key={lv.skill_code} style={{ display: "flex", alignItems: "center", gap: 10, margin: "10px 0" }}>
                    <div style={{ width: 170 }}>{lv.skill_name_fa} <span style={{ opacity: 0.5, fontSize: 11 }}>{lv.category}</span></div>
                    <div style={{ flex: 1, background: "rgba(255,255,255,.08)", borderRadius: 6, height: 14 }}>
                      <div style={{ width: `${lv.level}%`, height: "100%", borderRadius: 6,
                                    background: `linear-gradient(90deg,#6366f1,${levelColor(lv.level)})` }} />
                    </div>
                    <div style={{ width: 130, fontSize: 12 }}>
                      {fa(Math.round(lv.level))}/۱۰۰
                      {lv.evidence_count > 0 && <span style={{ opacity: 0.6 }}> — {fa(lv.evidence_count)} مدرک</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
          {me.careers?.length > 0 && (
            <Card title="تطبیق شغلی (از مهارت‌یار۳۶۰)">
              <BarChart data={me.careers.map((c: any) => ({ label: c.career_title, value: c.match_score }))} unit="٪" />
            </Card>
          )}
        </>
      )}
    </div>
  );
}
