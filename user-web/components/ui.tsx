'use client';
import type { ReactNode } from 'react';
import { avColor, initials, sevCls, SEV_COLOR } from '@/lib/format';

export const Pill = ({ sev, children }: { sev: string; children?: ReactNode }) => (
  <span className={`pill ${sevCls(sev)}`}>{children ?? sev}</span>
);
export const Av = ({ name, size = 32 }: { name: string; size?: number }) => (
  <div className="av" style={{ background: avColor(name), width: size, height: size, fontSize: size < 30 ? 11 : 12 }}>{initials(name)}</div>
);
export const Empty = ({ icon, children }: { icon: string; children: ReactNode }) => (
  <div className="card"><div className="empty"><div className="big">{icon}</div>{children}</div></div>
);
export const ErrorCard = ({ message }: { message: string }) => (
  <div className="card"><div className="empty"><div className="big">⚠️</div>Cannot reach the FinLend Ops API<br /><span className="mono">{message}</span></div></div>
);
export const Loading = () => <div className="card"><div className="empty">Loading…</div></div>;
export const SevBar = ({ pct, color }: { pct: number; color: string }) => (
  <div className="sevbar"><i style={{ width: `${Math.max(0, Math.min(100, pct))}%`, background: color }} /></div>
);
export const sevColor = (s: string) => SEV_COLOR[s] ?? '#60a5fa';
