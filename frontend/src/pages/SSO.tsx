// صفحات SSO: شبیه‌ساز سامانه مادر دانشجو۳۶۰ + دریافت توکن پس از callback
import React, { useEffect, useState } from "react";
import { api, setToken } from "../api";

// ---------- شبیه‌ساز ورود یکپارچه دانشجو۳۶۰ (همان جریان OIDC) ----------
export function SsoDemo({ onLogin, nav }: any) {
  const [identities, setIdentities] = useState<any[]>([]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState("");
  const state = new URLSearchParams((location.hash.split("?")[1] || "")).get("state") || "";

  useEffect(() => {
    api("/auth/sso/demo/identities").then((d) => setIdentities(d.items || [])).catch(() => {});
    if (!state) setErr("state نامعتبر است — دوباره از دکمه ورود یکپارچه شروع کنید");
  }, []);

  const go = async (email: string) => {
    setBusy(email); setErr("");
    try {
      const d = await api("/auth/sso/demo/authorize", { method: "POST", body: { state, email } });
      location.href = d.redirect; // → callback سمت سرور → /#/sso?token=...
    } catch (e: any) { setErr(e.message); setBusy(""); }
  };

  return (
    <div className="sso-wrap">
      <div className="sso-card">
        <div className="sso-brandrow">
          <div className="who">
            <div className="login-logo" style={{ margin: 0, width: 46, height: 46, fontSize: 18 }}>۳۶۰</div>
            <div><b>دانشجو۳۶۰</b><small>ورود یکپارچه — سامانه مادر</small></div>
          </div>
          <span className="sso-ver">v3.5</span>
        </div>
        <hr className="divider" style={{ margin: "12px 0" }} />
        <div style={{ fontSize: 13.5 }}>
          در حال انتقال به <b style={{ color: "#fcd34d" }}>صنعت‌یار۳۶۰</b> … پس از احراز هویت،
          دسترسی شما با نقش‌های کلید سامانه <code>sanatyar</code> اعمال می‌شود.
        </div>
        {err && <div className="alert error" style={{ marginTop: 12 }}>{err}</div>}
        <div className="sso-identities">
          {identities.map((i) => (
            <button key={i.email} className="sso-id" disabled={!!busy} onClick={() => go(i.email)}>
              <span><b>{i.name}</b><small className="muted">{i.label} — {i.email}</small></span>
              <span className="role-chip">{i.role}</span>
            </button>
          ))}
        </div>
        <p className="login-note">
          این صفحه شبیه‌ساز جریان OIDC برای تست بدون سرور دانشجو۳۶۰ است؛ در استقرار واقعی
          این مرحله روی سامانه مادر انجام می‌شود (Client ID: sanatyar360).
        </p>
      </div>
    </div>
  );
}

// ---------- دریافت توکن پس از callback و ورود ----------
export function SsoCallback({ onLogin }: any) {
  const [err, setErr] = useState("");
  useEffect(() => {
    const q = new URLSearchParams((location.hash.split("?")[1] || ""));
    const token = q.get("token");
    if (!token) { setErr("توکنی دریافت نشد"); return; }
    setToken(token);
    api("/auth/me")
      .then((d) => { location.hash = "/"; onLogin(d); })
      .catch((e) => setErr(e.message));
  }, []);
  return (
    <div className="sso-wrap">
      <div className="sso-card" style={{ textAlign: "center" }}>
        {err ? <div className="alert error">{err}</div> : (
          <div>
            <div className="login-logo" style={{ width: 50, height: 50, fontSize: 18 }}>✓</div>
            <h2 style={{ color: "#f1f5ff" }}>ورود یکپارچه موفق</h2>
            <p className="muted">در حال آماده‌سازی داشبورد صنعت‌یار۳۶۰…</p>
          </div>
        )}
      </div>
    </div>
  );
}
