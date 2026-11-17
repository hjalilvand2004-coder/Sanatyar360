// پیشنهادهای شخصی مسئله با دلیل (دانشجو/استاد)
import React, { useEffect, useState } from "react";
import { api, jalali, statusBadge, fa } from "../api";
import { Card, Empty, Alert } from "../ui";
import { useApp } from "../App";

export default function Recommendations() {
  const { nav } = useApp();
  const [items, setItems] = useState<any[]>([]);
  useEffect(() => { api("/me/recommended-problems").then((d) => setItems(d.items)).catch(() => {}); }, []);
  return (
    <div>
      <Alert kind="info">پیشنهادهای زیر خروجی موتور تطبیق قواعدی (نسخه ۱) بر مبنای مهارت‌های ثبت‌شده پروفایل شماست — «پیشنهاد سامانه» است و جایگزین جست‌وجوی شخصی یا تصمیم کارشناس نمی‌شود.</Alert>
      {items.length === 0 ? <Card><Empty text="هنوز پیشنهادی برای شما ساخته نشده؛ مهارت‌های پروفایل را در بخش حریم خصوصی کامل کنید" /></Card> : (
        items.map((r, i) => (
          <Card key={i} title={r.problem.title} extra={
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="match-score">{fa(Math.round(r.score * 100))}<span style={{ fontSize: 9 }}>%</span></span>
              {statusBadge(r.problem.status)}
            </span>}>
            <div className="muted" style={{ marginBottom: 8 }}>{r.problem.owner.name} • مهلت: {jalali(r.problem.application_deadline)}</div>
            <b>دلیل پیشنهاد:</b>
            <ul style={{ marginTop: 4 }}>{r.reasons.map((x: string, j: number) => <li key={j}>{x}</li>)}</ul>
            {r.missing.length > 0 && <div className="alert warn">مهارت‌های موجود در مسئله ولی ثبت‌نشده در پروفایل شما: {r.missing.join("، ")}</div>}
            <button className="btn primary" onClick={() => nav("/problem/" + r.problem.id)}>مشاهده و درخواست</button>
          </Card>
        ))
      )}
    </div>
  );
}
