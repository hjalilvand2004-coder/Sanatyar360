// هسته مسیریابی و چیدمان — هش‌روتر، سایدبار نقش‌محور، اعلان‌ها
import React, { useEffect, useState } from "react";
import { api, clearToken, setToken } from "./api";

export const Ctx = React.createContext<any>(null);
export const useApp = () => React.useContext(Ctx);

const DEMO_ACCOUNTS = [
  { email: "cio@nav.ac.ir", name: "دکتر لیلا احمدی", role: "مدیر دفتر ارتباط با صنعت" },
  { email: "expert@nav.ac.ir", name: "دکتر فرهاد قاسمی", role: "کارشناس حوزه تخصصی" },
  { email: "rep@pastechno.ir", name: "رضا محمدی", role: "نماینده صنعت (پارس‌تکنو)" },
  { email: "manager@pastechno.ir", name: "سارا کریمی", role: "مدیر سازمان صنعتی" },
  { email: "st1@nav.ac.ir", name: "امیر رضایی", role: "دانشجو — صنایع" },
  { email: "st2@nav.ac.ir", name: "نگار صادقی", role: "دانشجو — کامپیوتر" },
  { email: "prof.hosseini@nav.ac.ir", name: "دکتر مریم حسینی", role: "استاد — صنایع" },
  { email: "prof.karimi@nav.ac.ir", name: "دکتر حسن کریمی", role: "استاد — کامپیوتر" },
  { email: "comm@nav.ac.ir", name: "زهرا موسوی", role: "کارشناس تجاری‌سازی" },
  { email: "uniadmin@nav.ac.ir", name: "دکتر محمود رستمی", role: "مدیر دانشگاه" },
  { email: "rep@fezlavaran.ir", name: "علی نوری", role: "نماینده صنعت (فلزآوران)" },
  { email: "sysadmin@uiis-system.ir", name: "مدیر فنی سامانه", role: "مدیر فنی" },
];

function Login({ onLogin }: any) {
  const [email, setEmail] = useState("cio@nav.ac.ir");
  const [pass, setPass] = useState("uiis1234");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const [sso, setSso] = useState<any>(null);
  const go = async (e?: string, p?: string) => {
    setBusy(true); setErr("");
    try {
      const data = await api("/auth/login", { method: "POST", body: { email: e || email, password: p || pass } });
      setToken(data.access_token);
      onLogin(data);
    } catch (ex: any) { setErr(ex.message); } finally { setBusy(false); }
  };
  useEffect(() => {
    // ورود یکپارچه — قرارداد مشترک زیرسیستم‌های اکوسیستم دانشجویار۳۶۰
    const q = new URLSearchParams(location.search);
    const errs: Record<string, string> = {
      invalid_state: "نشست ورود یکپارچه منقضی شده است — دوباره تلاش کنید",
      invalid_code: "کد احراز نامعتبر بود — دوباره تلاش کنید",
      provider_error: "ارتباط با سامانه مادر دانشجو۳۶۰ ناموفق بود — بعداً تلاش کنید",
      no_email: "حساب شما فاقد ایمیل سازمانی است",
      sso_user_unknown: "این حساب در صنعت‌یار۳۶۰ ثبت نشده است",
    };
    const ssoErr = q.get("sso_error");
    if (ssoErr) setErr(errs[ssoErr] || "ورود یکپارچه ناموفق بود؛ دوباره تلاش کنید");
    const tok = q.get("sso_token");
    if (tok) {
      // مدل سبک: توکن صادرشده مرکز SSO/سامانه مادر در URL → پذیرش و ساخت نشست محلی
      api("/auth/sso/accept", { method: "POST", body: { token: tok } })
        .then((d) => { setToken(d.access_token); onLogin(d); })
        .catch((e: any) => setErr(e.message));
      history.replaceState({}, "", location.pathname);
      return;
    }
    api("/auth/sso/config").then((d) => {
      setSso(d);
      // شروع خودکار جریان وقتی از پرتال مادر با ?sso=1 آمده (گارد یک‌بار اجرا)
      if (d.enabled && q.get("sso") === "1" && !ssoErr && !sessionStorage.getItem("sso_auto_started")) {
        sessionStorage.setItem("sso_auto_started", "1");
        location.href = d.login_url || "/api/v1/auth/sso/login";
      }
    }).catch(() => {});
  }, []);
  return (
    <div className="login-wrap">
      <div className="blob b1" /><div className="blob b2" /><div className="blob b3" />
      <div className="login-card">
        <div className="login-logo">۳۶۰</div>
        <h2>صنعت‌یار۳۶۰</h2>
        <p className="subtitle">اتصال دانشجو به صنعت — زیرسیستم دانشجو۳۶۰</p>
        {err && <div className="alert error">{err}</div>}
        {sso?.enabled !== false && (
          <a className="sso-btn" href={sso?.login_url || "/api/v1/auth/sso/login"}>
            <span className="sso-ico">🎓</span>
            <span className="sso-txt">
              <b>{sso?.label || "ورود یکپارچه سازمانی"}</b>
              <small>{sso?.sub_label || "با حساب پرتال دانشجویار۳۶۰ — بدون تکرار رمز"}</small>
            </span>
          </a>
        )}
        <div className="login-or">یا ورود محلی</div>
        <div className="field"><label>ایمیل سازمانی</label>
          <input value={email} onChange={(e: any) => setEmail(e.target.value)} onKeyDown={(e: any) => e.key === "Enter" && go()} /></div>
        <div className="field"><label>رمز عبور</label>
          <input type="password" value={pass} onChange={(e: any) => setPass(e.target.value)} onKeyDown={(e: any) => e.key === "Enter" && go()} /></div>
        <button className="btn primary" style={{ width: "100%" }} disabled={busy} onClick={() => go()}>
          {busy ? "در حال ورود…" : "ورود"}
        </button>
        <div className="login-or">حساب‌های نمونه (رمز: uiis1234)</div>
        <div className="demo-accounts">
          {DEMO_ACCOUNTS.map((a) => (
            <button key={a.email} className="demo-acc" onClick={() => { setEmail(a.email); setPass("uiis1234"); go(a.email, "uiis1234"); }}>
              <span><b>{a.name}</b><br />{a.role}</span>
              <span className="muted">{a.email}</span>
            </button>
          ))}
        </div>
        <p className="login-note">
          ثبت در پنل «مدیریت سامانه‌ها»ی دانشجویار۳۶۰ — کلید: <code>sanatyar</code> ·
          Client ID: <code>sanatyar360</code> · آدرس ورود: <code>http://188.212.96.235:8092/api/v1/auth/sso/login</code>
        </p>
      </div>
    </div>
  );
}

const NAV = [
  { group: "اصلی", items: [
    { route: "/", label: "داشبورد", icon: "▦", roles: "all" },
    { route: "/problems", label: "بازار مسائل صنعت", icon: "▤", roles: "all" },
    { route: "/notifications", label: "اعلان‌ها", icon: "🔔", roles: "all" },
  ]},
  { group: "دانشجو و استاد", items: [
    { route: "/recommendations", label: "پیشنهادهای سامانه", icon: "✦", roles: ["student", "professor"] },
    { route: "/applications", label: "درخواست‌های من", icon: "✉", roles: ["student", "professor"] },
    { route: "/maharat", label: "مهارت‌یار۳۶۰", icon: "🧩", roles: ["student", "professor"] },
  ]},
  { group: "صنعت", items: [
    { route: "/my-problems", label: "مسائل سازمان من", icon: "▤", roles: ["industry_rep", "industry_manager"] },
    { route: "/problems/new", label: "ثبت مسئله جدید", icon: "＋", roles: ["industry_rep", "industry_manager"] },
  ]},
  { group: "دفتر ارتباط با صنعت", items: [
    { route: "/review", label: "صف بررسی", icon: "☑", roles: ["cio_manager", "cio_expert", "university_admin", "sys_admin"] },
    { route: "/organizations", label: "سازمان‌ها", icon: "🖇", roles: "all" },
    { route: "/commercialization", label: "تجاری‌سازی پژوهش", icon: "◈", roles: ["cio_manager", "cio_expert", "comm_expert", "professor", "university_admin", "sys_admin"] },
    { route: "/analytics", label: "تحلیل و شاخص‌ها", icon: "📈", roles: ["cio_manager", "cio_expert", "university_admin", "policy_maker", "sys_admin", "comm_expert"] },
  ]},
  { group: "پیگیری", items: [
    { route: "/collaborations", label: "همکاری‌های من", icon: "⛓", roles: "all" },
  ]},
  { group: "مدیریت سامانه", items: [
    { route: "/privacy", label: "حریم خصوصی", icon: "⛨", roles: "all" },
    { route: "/audit", label: "حسابرسی عملیات", icon: "🧾", roles: ["sys_admin"] },
  ]},
];

export default function App() {
  const [me, setMe] = useState<any>(null);
  const [booting, setBooting] = useState(true);
  const [route, setRoute] = useState(location.hash.slice(1) || "/");
  const [notifCount, setNotifCount] = useState(0);
  const [toast, setToast] = useState<string>("");

  const refreshNotifs = () => api("/notifications").then((d) => setNotifCount(d.unread)).catch(() => {});

  useEffect(() => {
    const h = () => setRoute(location.hash.slice(1) || "/");
    addEventListener("hashchange", h);
    return () => removeEventListener("hashchange", h);
  }, []);
  useEffect(() => {
    if (localStorage.getItem("uiis_token")) {
      api("/auth/me").then((d) => { setMe(d); refreshNotifs(); }).catch(() => clearToken());
    }
    setBooting(false);
  }, []);
  useEffect(() => { window.scrollTo(0, 0); }, [route]);
  useEffect(() => {
    const t = setInterval(() => me && refreshNotifs(), 20000);
    return () => clearInterval(t);
  }, [me]);

  const notify = (msg: string) => { setToast(msg); setTimeout(() => setToast(""), 3500); };
  const nav = (r: string) => { location.hash = r; setRoute(r); };

  if (booting) return null;
  // مسیرهای SSO — قبل از بررسی احراز هویت
  if (route.startsWith("/sso-demo")) return <SsoDemo onLogin={(d: any) => { setMe(d); refreshNotifs(); }} nav={nav} />;
  if (route.startsWith("/sso")) return <SsoCallback onLogin={(d: any) => { setMe(d); refreshNotifs(); }} />;
  if (!me) return <Login onLogin={(d: any) => { setMe(d); refreshNotifs(); nav("/"); }} />;

  const myRoles = new Set(me.memberships.map((m: any) => m.role));
  const userType = me.user.user_type;
  const hasRole = (roles: any) =>
    roles === "all" ? true :
    roles.some((r: string) =>
      myRoles.has(r) || (r === "student" && userType === "student") || (r === "professor" && userType === "professor"));

  const Page = PAGES[route] || PAGES["/"];
  const pageProps = { route, nav };
  // مسیرهای جزئیات: /problem/{id} و غیره
  let ResolvedPage: any = Page;
  if (route.startsWith("/problem/")) ResolvedPage = PAGES["/problem"];
  if (route.startsWith("/application/")) ResolvedPage = PAGES["/application"];
  if (route.startsWith("/collaboration/")) ResolvedPage = PAGES["/collaboration"];

  return (
    <Ctx.Provider value={{ me, nav, route, notify, refreshNotifs, myRoles, userType }}>
      <div className="shell">
        <aside className="sidebar">
          <div className="brand">
            <div className="brand-logo">۳۶۰</div>
            <div><b>صنعت‌یار۳۶۰</b><span>اتصال دانشجو به صنعت</span></div>
          </div>
          {NAV.filter((g) => g.items.some((i) => hasRole(i.roles))).map((g) => (
            <div key={g.group}>
              <div className="nav-section">{g.group}</div>
              {g.items.filter((i) => hasRole(i.roles)).map((i) => (
                <button key={i.route}
                  className={"nav-item" + ((route === i.route || (i.route !== "/" && route.startsWith(i.route))) ? " active" : "")}
                  onClick={() => nav(i.route)}>
                  <span className="ico">{i.icon}</span>{i.label}
                </button>
              ))}
            </div>
          ))}
        </aside>
        <main className="main">
          <div className="topbar">
            <h1>{PAGE_TITLES[route] || "داشبورد"}</h1>
            <div className="userbox">
              <button className="bell" onClick={() => nav("/notifications")}>
                🔔{notifCount > 0 && <span className="dot">{notifCount.toLocaleString("fa-IR")}</span>}
              </button>
              <div className="avatar">{me.user.full_name.slice(0, 2)}</div>
              <div style={{ lineHeight: 1.4 }}>
                <div style={{ fontWeight: 700 }}>{me.user.full_name}</div>
                <small>{me.memberships[0]?.role_label} — {me.memberships[0]?.organization_name}</small>
              </div>
              <button className="btn sm" onClick={() => { clearToken(); setMe(null); }}>خروج</button>
            </div>
          </div>
          <ResolvedPage {...pageProps} />
          {toast && <div className="modal-overlay" style={{ background: "transparent", alignItems: "end", gridTemplateRows: "1fr auto", justifyItems: "center" }}>
            <div className="alert ok" style={{ marginBottom: 20 }}>{toast}</div>
          </div>}
        </main>
      </div>
    </Ctx.Provider>
  );
}

const PAGE_TITLES: Record<string, string> = {
  "/": "داشبورد", "/problems": "بازار مسائل صنعت", "/problems/new": "ثبت مسئله صنعتی جدید",
  "/my-problems": "مسائل سازمان من", "/recommendations": "پیشنهادهای سامانه",
  "/applications": "درخواست‌های من", "/collaborations": "همکاری‌های من",
  "/review": "صف بررسی دفتر ارتباط با صنعت", "/organizations": "سازمان‌ها",
  "/commercialization": "غربالگری فرصت‌های تجاری‌سازی", "/analytics": "تحلیل و شاخص‌ها",
  "/notifications": "اعلان‌ها", "/privacy": "حریم خصوصی و رضایت‌ها", "/audit": "حسابرسی عملیات",
};

// صفحات در فایل‌های جداگانه
import Dashboard from "./pages/Dashboard";
import ProblemList from "./pages/ProblemList";
import ProblemDetail from "./pages/ProblemDetail";
import ProblemNew from "./pages/ProblemNew";
import Applications from "./pages/Applications";
import AppDetail from "./pages/AppDetail";
import Recommendations from "./pages/Recommendations";
import Collaborations from "./pages/Collaborations";
import CollabDetail from "./pages/CollabDetail";
import ReviewQueue from "./pages/ReviewQueue";
import Organizations from "./pages/Organizations";
import Commercialization from "./pages/Commercialization";
import Analytics from "./pages/Analytics";
import Maharat from "./pages/Maharat";
import { Notifications, Privacy, Audit } from "./pages/Misc";
import { SsoDemo, SsoCallback } from "./pages/SSO";

const PAGES: Record<string, any> = {
  "/": Dashboard, "/problems": ProblemList, "/my-problems": ProblemList,
  "/problems/new": ProblemNew, "/recommendations": Recommendations,
  "/applications": Applications, "/collaborations": Collaborations,
  "/review": ReviewQueue, "/organizations": Organizations,
  "/commercialization": Commercialization, "/analytics": Analytics,
  "/maharat": Maharat,
  "/notifications": Notifications, "/privacy": Privacy, "/audit": Audit,
  "/problem": ProblemDetail, "/application": AppDetail, "/collaboration": CollabDetail,
};
