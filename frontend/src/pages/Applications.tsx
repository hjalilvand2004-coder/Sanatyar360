// درخواست‌های همکاری من (دانشجو/استاد) + بررسی متقاضیان (صنعت/دفتر) در صفحه مسئله
import React, { useEffect, useState } from "react";
import { api, jalali, statusBadge, label } from "../api";
import { Card, Empty, Alert } from "../ui";
import { useApp } from "../App";

export default function Applications() {
  const { nav } = useApp();
  const [items, setItems] = useState<any[]>([]);
  useEffect(() => { api("/applications").then((d) => setItems(d.items)).catch(() => {}); }, []);
  return (
    <div>
      <Alert kind="info">
        پس از پذیرش درخواست، دفتر ارتباط با صنعت یا نماینده صنعت پروژه همکاری را ایجاد می‌کند و وضعیت اینجا پیگیری می‌شود.
      </Alert>
      <Card title="درخواست‌های همکاری من">
        {items.length === 0 ? <Empty text="درخواستی ثبت نشده است — از بازار مسائل شروع کنید" /> : (
          <div className="tbl-wrap"><table className="tbl">
            <thead><tr><th>مسئله</th><th>نقش</th><th>وضعیت</th><th>تیم</th><th>دلیل تصمیم</th><th>تاریخ</th><th></th></tr></thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id}>
                  <td><a href={"#/problem/" + a.problem_id}>{a.problem_title}</a></td>
                  <td>{a.proposed_role || "—"}</td>
                  <td>{statusBadge(a.status)}</td>
                  <td>{a.team_name || "—"}</td>
                  <td className="muted" style={{ maxWidth: 220 }}>{a.decision_reason || "—"}</td>
                  <td>{jalali(a.created_at)}</td>
                  <td><button className="btn sm" onClick={() => nav("/application/" + a.id)}>جزئیات</button></td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )}
      </Card>
    </div>
  );
}
