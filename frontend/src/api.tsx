// لایه ارتباط با API — توکن، خطاهای ساختاریافته، تاریخ شمسی
const API = "/api/v1";
let TOKEN = localStorage.getItem("uiis_token") || "";

export function setToken(t: string) { TOKEN = t; localStorage.setItem("uiis_token", t); }
export function clearToken() { TOKEN = ""; localStorage.removeItem("uiis_token"); }

export async function api(path: string, opts: any = {}) {
  const res = await fetch(API + path, {
    method: opts.method || "GET",
    headers: {
      "Content-Type": "application/json",
      ...(TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {}),
    },
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = (data && (data.message || data.detail?.message)) || `خطای ${res.status}`;
    const err: any = new Error(msg);
    err.code = data?.code || data?.detail?.code;
    err.status = res.status;
    throw err;
  }
  return data;
}

export const fa = (n: any) =>
  n === null || n === undefined || n === "" ? "—" : Number(n).toLocaleString("fa-IR");

export const jalali = (iso: string | null | undefined, withTime = false) => {
  if (!iso) return "—";
  try {
    const d = new Date(iso);
    const s = new Intl.DateTimeFormat("fa-IR", {
      calendar: "persian", year: "numeric", month: "2-digit", day: "2-digit",
      ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
    }).format(d);
    return s;
  } catch { return iso; }
};

// برچسب‌های فارسی وضعیت‌ها
export const LABELS: Record<string, string> = {
  draft: "پیش‌نویس", submitted: "ارسال‌شده", under_review: "در بررسی",
  needs_revision: "نیازمند اصلاح", published: "منتشرشده",
  applications_closed: "بسته‌شده فراخوان", converted_to_project: "تبدیل به همکاری",
  rejected: "ردشده", withdrawn: "پس‌گرفته‌شده", expired: "منقضی", archived: "آرشیو",
  shortlisted: "فهرست کوتاه", accepted: "پذیرفته‌شده",
  proposed: "پیشنهادی", agreement_pending: "در انتظار توافق", active: "فعال",
  on_hold: "متوقف", completed: "تکمیل‌شده", terminated: "خاتمه‌یافته",
  pending: "در انتظار", verified: "تأییدشده", suspended: "معلق",
  approved: "تأیید", approve: "تأیید", done: "انجام‌شده", late: "با تأخیر", cancelled: "لغوشده",
  invited: "دعوت‌شده", declined: "عدم پذیرش",
  public: "عمومی", registered_users: "کاربران ثبت‌نام‌شده",
  selected_participants: "شرکت‌کنندگان منتخب", confidential: "محرمانه",
  onsite: "حضوری", remote: "دورکاری", hybrid: "ترکیبی",
  industry: "صنعت", university: "دانشگاه",
  suggested: "پیشنهادی", under_expert_review: "در ارزیابی متخصص",
  expert_approved: "تأیید متخصص", in_negotiation: "در مذاکره",
  revision_requested: "نیازمند اصلاح",
  proceed: "ادامه فرآیند", need_info: "نیازمند اطلاعات", reject: "رد",
  student: "دانشجو", professor: "استاد", staff: "کارمند",
  industry_rep: "نماینده صنعت", industry_manager: "مدیر سازمان صنعتی",
  cio_manager: "مدیر دفتر ارتباط با صنعت", cio_expert: "کارشناس حوزه تخصصی",
  comm_expert: "کارشناس تجاری‌سازی", university_admin: "مدیر دانشگاه",
  policy_maker: "سیاست‌گذار", sys_admin: "مدیر فنی",
  self_declared: "خوداعلامی", imported: "درون‌ریزی", contract: "قرارداد", nda: "عدم افشا",
};

export const label = (k: string | null | undefined) => (k ? LABELS[k] || k : "—");

export const statusBadge = (s: string | null | undefined) => {
  const map: Record<string, string> = {
    draft: "gray", submitted: "blue", under_review: "amber", needs_revision: "red",
    published: "green", applications_closed: "gray", converted_to_project: "violet",
    rejected: "red", withdrawn: "gray", expired: "gray", archived: "gray",
    shortlisted: "violet", accepted: "green", proposed: "gray",
    agreement_pending: "amber", active: "green", on_hold: "amber",
    completed: "violet", terminated: "red",
    pending: "amber", verified: "green", suspended: "red",
    public: "green", registered_users: "blue", selected_participants: "amber", confidential: "red",
    submitted_d: "blue", invited: "blue", done: "green", late: "red", cancelled: "gray",
    suggested: "blue", under_expert_review: "amber", expert_approved: "green",
    in_negotiation: "violet", revision_requested: "red",
  };
  const cls = map[s || ""] || "gray";
  return <span className={`badge ${cls}`}>{label(s)}</span>;
};

export const money = (v: any, c: string) => {
  if (v === null || v === undefined) return null;
  return `${fa(v)} ${c === "IRR" ? "ریال" : c}`;
};
