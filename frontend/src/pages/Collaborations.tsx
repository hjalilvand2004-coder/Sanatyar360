// فهرست همکاری‌ها
import React, { useEffect, useState } from "react";
import { api, jalali, statusBadge } from "../api";
import { Card, Empty, Alert } from "../ui";
import { useApp } from "../App";

export default function Collaborations() {
  const { nav, me } = useApp();
  const [items, setItems] = useState<any[]>([]);
  useEffect(() => { api("/collaborations").then((d) => setItems(d.items)).catch(() => {}); }, []);
  return (
    <div>
      <Alert kind="info">
        تابلو وظایف، ثبت ساعت و گفت‌وگوی روزانه در سامانه مدیریت پروژه تخصصی باقی می‌ماند؛ اینجا شناسنامه همکاری،
        نقاط عطف قراردادی، خروجی‌های پذیرفته‌شده و وضعیت کلی نگه داشته می‌شود.
      </Alert>
      <Card title="پروژه‌های همکاری">
        {items.length === 0 ? <Empty /> : (
          <div className="tbl-wrap"><table className="tbl">
            <thead><tr><th>کد</th><th>عنوان</th><th>مسئله مبدأ</th><th>وضعیت</th><th>شروع</th></tr></thead>
            <tbody>
              {items.map((p) => (
                <tr key={p.id} style={{ cursor: "pointer" }} onClick={() => nav("/collaboration/" + p.id)}>
                  <td><code>{p.code}</code></td>
                  <td><b>{p.title}</b></td>
                  <td className="muted">{p.problem_id ? "مربوط به مسئله ثبت‌شده" : "—"}</td>
                  <td>{statusBadge(p.status)}</td>
                  <td>{jalali(p.started_at)}</td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </Card>
    </div>
  );
}
