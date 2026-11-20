'use client';
import { useState } from 'react';
import { api } from '@/lib/api';
import { useLoad, useNow } from '@/lib/hooks';
import { useAlerts } from '@/components/Shell';
import { Empty, ErrorCard, Loading } from '@/components/ui';
import { DEADLINE_HOURS, DEADLINE_LABEL, REPORT_LABEL, alertType, countdown, ts } from '@/lib/format';

export default function Deadlines() {
  const { alerts, error } = useAlerts();
  const [sel, setSel] = useState<string | null>(null), [rep, setRep] = useState<string | null>(null), [copied, setCopied] = useState(false);
  const now = useNow(1000);
  const id = alerts?.find((a) => a.alert_id === sel)?.alert_id ?? alerts?.[0]?.alert_id;
  const reports = useLoad(() => (id ? api.getReports(id) : Promise.resolve([])), [id], 5000);
  if (error && !alerts) return <ErrorCard message={error} />;
  if (!alerts) return <Loading />;
  if (!alerts.length) return <Empty icon="🕒">No incident needs regulator reporting yet.</Empty>;
  const a = alerts.find((x) => x.alert_id === id)!;
  const list = reports.data ?? [];
  const cur = list.find((r) => r.report_type === rep) ?? list[0];
  return (
    <>
      <div className="row" style={{ marginBottom: 16 }}><span className="muted">Incident</span>
        <select style={{ width: 'auto' }} value={id} onChange={(e) => { setSel(e.target.value); setRep(null); }}>
          {alerts.map((x) => <option key={x.alert_id} value={x.alert_id}>{alertType(x)} · {x.severity} · {x.alert_id}</option>)}</select></div>
      <div className="grid g3">
        {a.deadlines.map((d) => { const h = DEADLINE_HOURS[d.body] ?? 6; const c = countdown(d.due_at, h, now); return (
          <div key={d.body} className="card"><h3>{DEADLINE_LABEL[d.body] ?? d.body}</h3>
            <div className="cd" style={{ color: c.txt === 'Overdue' ? '#fda4af' : undefined }}>{c.txt}</div>
            <div className="muted" style={{ fontSize: 12, marginTop: 4 }}>due {ts(d.due_at)} IST · {h} h from detection</div>
            <div className="sevbar" style={{ marginTop: 12 }}><i style={{ width: `${c.p * 100}%`, background: h <= 6 ? 'linear-gradient(90deg,#fb923c,#f43f5e)' : 'linear-gradient(90deg,#60a5fa,#2dd4bf)' }} /></div></div>); })}</div>
      <div className="card" style={{ marginTop: 16 }}><h3>Draft reports · generated at detection</h3>
        {cur ? <>
          <div className="tabs">{list.map((r) => <button key={r.report_type} className={`btn ${r.report_type === cur.report_type ? 'on' : ''}`} onClick={() => setRep(r.report_type)}>{REPORT_LABEL[r.report_type] ?? r.report_type}</button>)}</div>
          <div className="row" style={{ marginBottom: 8 }}><span className="muted">Status <b style={{ color: 'var(--ink)' }}>{cur.status}</b></span><span className="sp" />
            <button className="btn" onClick={async () => { await navigator.clipboard.writeText(cur.body_md); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>{copied ? 'Copied' : 'Copy'}</button></div>
          <pre className="report">{cur.body_md}</pre></> : <div className="muted">Reports are being generated…</div>}
        <p className="dim" style={{ fontSize: 12, marginTop: 12 }}>Drafts only. A human reviews and files them. DPDP is presented as readiness and controls, not legal advice.</p></div>
    </>
  );
}
