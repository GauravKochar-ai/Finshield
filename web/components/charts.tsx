import type { ReactNode } from 'react';
import { fmt } from '@/lib/format';

export function Ring({ v, max, color, size = 120, label = '', sub = '' }: { v: number; max: number; color: string; size?: number; label?: ReactNode; sub?: string }) {
  const r = size / 2 - 9, c = 2 * Math.PI * r, p = Math.max(0, Math.min(1, v / max));
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size / 2} cy={size / 2} r={r} stroke="#1c2945" strokeWidth="10" fill="none" />
      <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth="10" fill="none" strokeLinecap="round"
        strokeDasharray={`${c * p} ${c}`} transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: 'stroke-dasharray .6s' }} />
      <text x="50%" y={size / 2 + (sub ? 2 : 8)} textAnchor="middle" fill="#e7ecf6" fontSize={size / 4.2} fontWeight="800">{label}</text>
      {sub && <text x="50%" y={size / 2 + 20} textAnchor="middle" fill="#8e9ab5" fontSize="11">{sub}</text>}
    </svg>
  );
}

export function Donut({ parts, size = 118, unit = 'controls' }: { parts: { v: number; c: string }[]; size?: number; unit?: string }) {
  const tot = parts.reduce((a, p) => a + p.v, 0), r = size / 2 - 10, c = 2 * Math.PI * r;
  let off = 0;
  return (
    <svg width={size} height={size}>
      <circle cx={size / 2} cy={size / 2} r={r} stroke="#1c2945" strokeWidth="12" fill="none" />
      {parts.map((p, i) => {
        const l = (c * p.v) / (tot || 1);
        const el = <circle key={i} cx={size / 2} cy={size / 2} r={r} stroke={p.c} strokeWidth="12" fill="none"
          strokeDasharray={`${Math.max(0, l - 2)} ${c}`} strokeDashoffset={-off} transform={`rotate(-90 ${size / 2} ${size / 2})`} />;
        off += l;
        return el;
      })}
      <text x="50%" y="53%" textAnchor="middle" fill="#e7ecf6" fontSize="22" fontWeight="800">{tot}</text>
      <text x="50%" y="68%" textAnchor="middle" fill="#8e9ab5" fontSize="10.5">{unit}</text>
    </svg>
  );
}

export function HBars({ items }: { items: { k: string; v: number; c?: string }[] }) {
  const mx = Math.max(1, ...items.map((i) => i.v));
  return (
    <>
      {items.map((i) => (
        <div key={i.k} style={{ margin: '9px 0' }}>
          <div className="row" style={{ justifyContent: 'space-between', fontSize: 12.5 }}><span>{i.k}</span><b>{fmt(i.v)}</b></div>
          <div className="sevbar" style={{ marginTop: 5 }}><i style={{ width: `${(i.v / mx) * 100}%`, background: i.c || 'linear-gradient(90deg,#60a5fa,#2dd4bf)' }} /></div>
        </div>
      ))}
    </>
  );
}

/** Events over time. Buckets the given timestamps (all events vs. flagged ones) into B slots across their own span. */
export function AreaChart({ times, bad, w = 560, h = 150 }: { times: number[]; bad: number[]; w?: number; h?: number }) {
  const B = 36;
  const all = times.length ? times : [Date.now()];
  const min = Math.min(...all), span = Math.max(1, Math.max(...all) - min);
  const bucket = (arr: number[]) => {
    const b = new Array(B).fill(0);
    arr.forEach((t) => { b[Math.min(B - 1, Math.floor(((t - min) / span) * B))] += 1; });
    return b;
  };
  const a = bucket(times), d = bucket(bad), mx = Math.max(4, ...a);
  const x = (i: number) => i * (w / (B - 1)), y = (v: number) => h - 12 - (v / mx) * (h - 26);
  const line = (arr: number[]) => arr.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  const clock = (t: number) => new Date(t + 5.5 * 3600e3).toISOString().slice(11, 16);
  return (
    <svg width="100%" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ display: 'block' }}>
      <defs>
        <linearGradient id="ga" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#60a5fa" stopOpacity=".45" /><stop offset="1" stopColor="#60a5fa" stopOpacity="0" /></linearGradient>
        <linearGradient id="gb" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stopColor="#f43f5e" stopOpacity=".55" /><stop offset="1" stopColor="#f43f5e" stopOpacity="0" /></linearGradient>
      </defs>
      {[0.25, 0.5, 0.75].map((g) => <line key={g} x1="0" x2={w} y1={(h - 12) * g} y2={(h - 12) * g} stroke="#1c2945" />)}
      <path d={`${line(a)} L${w} ${h - 12} L0 ${h - 12}Z`} fill="url(#ga)" /><path d={line(a)} stroke="#60a5fa" strokeWidth="2" fill="none" />
      <path d={`${line(d)} L${w} ${h - 12} L0 ${h - 12}Z`} fill="url(#gb)" /><path d={line(d)} stroke="#f43f5e" strokeWidth="2" fill="none" />
      <text x="0" y={h} fill="#64718e" fontSize="10">{times.length ? clock(min) : ''}</text>
      <text x={w} y={h} fill="#64718e" fontSize="10" textAnchor="end">{times.length ? clock(min + span) : ''}</text>
    </svg>
  );
}
