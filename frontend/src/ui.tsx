// اجزای مشترک رابط کاربری
import React from "react";

export const Card = ({ title, children, extra, style }: any) => (
  <div className="card" style={style}>
    {(title || extra) && (
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10, flexWrap: "wrap", gap: 8 }}>
        {title && <h3 style={{ margin: 0 }}>{title}</h3>}
        {extra}
      </div>
    )}
    {children}
  </div>
);

export const Kpi = ({ val, lbl, color }: any) => (
  <div className="card kpi">
    <div className="val" style={color ? { color } : undefined}>{val}</div>
    <div className="lbl">{lbl}</div>
  </div>
);

export const Field = ({ label, children, hint }: any) => (
  <div className="field">
    <label>{label}</label>
    {children}
    {hint && <div className="hint">{hint}</div>}
  </div>
);

export const Modal = ({ title, onClose, children }: any) => (
  <div className="modal-overlay" onClick={onClose}>
    <div className="modal" onClick={(e: any) => e.stopPropagation()}>
      <h3>{title}</h3>
      {children}
    </div>
  </div>
);

export const Empty = ({ text = "داده‌ای برای نمایش وجود ندارد" }: any) => (
  <div className="empty">{text}</div>
);

export const Alert = ({ kind = "info", children }: any) => (
  <div className={`alert ${kind}`}>{children}</div>
);

export const Flow = ({ states, current }: any) => {
  const idx = states.indexOf(current);
  return (
    <div className="flow">
      {states.map((s: string, i: number) => (
        <React.Fragment key={s}>
          <span className={"fs " + (i < idx ? "done" : i === idx ? "now" : "")}>{s}</span>
          {i < states.length - 1 && <span className="arr">←</span>}
        </React.Fragment>
      ))}
    </div>
  );
};

export const BarChart = ({ data, unit = "" }: any) => {
  if (!data.length) return <Empty />;
  const max = Math.max(...data.map((d: any) => d.value)) || 1;
  return (
    <div>
      {data.map((d: any, i: number) => (
        <div className="barchart-row" key={i}>
          <span className="bl">{d.label}</span>
          <div className="bt"><div style={{ width: `${(d.value / max) * 100}%` }} /></div>
          <span className="bv">{d.value.toLocaleString("fa-IR")}{unit}</span>
        </div>
      ))}
    </div>
  );
};

export const LineChart = ({ data, width = 560, height = 180 }: any) => {
  // نمودار خطی ساده SVG
  if (!data.length) return <Empty />;
  const max = Math.max(...data.map((d: any) => d.value)) || 1;
  const stepX = (width - 60) / Math.max(1, data.length - 1);
  const pts = data.map((d: any, i: number) => [30 + i * stepX, height - 30 - (d.value / max) * (height - 60)]);
  const path = pts.map((p, i) => (i === 0 ? "M" : "L") + p[0] + "," + p[1]).join(" ");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "auto", maxWidth: width }}>
      {[0.25, 0.5, 0.75, 1].map((f, i) => (
        <line key={i} x1={30} x2={width - 20} y1={height - 30 - f * (height - 60)} y2={height - 30 - f * (height - 60)}
          stroke="#e2e8f0" strokeDasharray="3,4" />
      ))}
      <path d={path} fill="none" stroke="#4f46e5" strokeWidth="2.5" />
      {pts.map((p, i) => (
        <g key={i}>
          <circle cx={p[0]} cy={p[1]} r="4" fill="#0d9488" />
          <text x={p[0]} y={p[1] - 10} fontSize="10" textAnchor="middle" fill="#475569">
            {data[i].value.toLocaleString("fa-IR")}
          </text>
          <text x={p[0]} y={height - 10} fontSize="10.5" textAnchor="middle" fill="#64748b">
            {data[i].label}
          </text>
        </g>
      ))}
    </svg>
  );
};

export const NetworkGraph = ({ nodes, edges }: any) => {
  // چیدمان دایره‌ای ساده با SVG
  const n = nodes.length;
  if (!n) return <Empty />;
  const W = 640, H = 420, cx = W / 2, cy = H / 2, R = Math.min(W, H) / 2 - 70;
  const pos: Record<string, { x: number; y: number }> = {};
  nodes.forEach((node: any, i: number) => {
    const a = (2 * Math.PI * i) / n - Math.PI / 2;
    pos[node.id] = { x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) };
  });
  const colorOf = (k: string) => (k === "industry" ? "#0d9488" : k === "university" ? "#4f46e5" : "#f59e0b");
  return (
    <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto" }}>
      {edges.map((e: any, i: number) => {
        const a = pos[e.from], b = pos[e.to];
        if (!a || !b) return null;
        return (
          <g key={i}>
            <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#94a3b8" strokeWidth={1 + Math.min(4, e.weight)}
              opacity={0.75} strokeDasharray={e.weight > 1 ? "" : "4,3"} />
            {e.weight > 1 && (
              <text x={(a.x + b.x) / 2} y={(a.y + b.y) / 2 - 6} fontSize="11" textAnchor="middle" fill="#475569">
                {e.weight.toLocaleString("fa-IR")}
              </text>
            )}
          </g>
        );
      })}
      {nodes.map((node: any, i: number) => {
        const p = pos[node.id];
        const c = colorOf(node.kind);
        return (
          <g key={node.id}>
            <circle cx={p.x} cy={p.y} r={9 + Math.min(10, (node.projects || 0) * 2)} fill={c} opacity="0.92" />
            <text x={p.x} y={p.y + (node.kind === "academic_lead" ? 26 : 30)} fontSize="11.5" textAnchor="middle"
              fill="#1e293b">{node.label.length > 18 ? node.label.slice(0, 17) + "…" : node.label}</text>
            <text x={p.x} y={p.y + 44} fontSize="10" textAnchor="middle" fill="#64748b">
              {(node.projects || 0).toLocaleString("fa-IR")} پروژه
            </text>
          </g>
        );
      })}
      <g>
        <circle cx={W - 180} cy={18} r={7} fill="#0d9488" />
        <text x={W - 168} y={22} fontSize="11">سازمان صنعتی</text>
        <circle cx={W - 90} cy={18} r={7} fill="#4f46e5" />
        <text x={W - 78} y={22} fontSize="11">دانشگاه</text>
        <circle cx={W - 262} cy={18} r={7} fill="#f59e0b" />
        <text x={W - 250} y={22} fontSize="11">مسئول علمی</text>
      </g>
    </svg>
  );
};
