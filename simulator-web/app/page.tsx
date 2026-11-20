'use client';
import { useState } from 'react';
import { api, type SimulateResult } from '@/lib/api';
import { Pill } from '@/components/ui';

const SCENARIOS: { id: string; t: string; who: string; src: string; exp: string; hero?: boolean; steps: string[] }[] = [
  { id: 'SC-01', hero: true, t: 'Ops admin bulk-exports KYC files at night and uploads them outside', who: 'u-017 · ops admin', src: 'Sign-in, IAM, KYC store', exp: 'CRITICAL 96', steps: ['23:40 emergency role, no approval, from a new device and a second city', '212 KYC files in 15 min (106× usual)', 'Upload to an external file share'] },
  { id: 'SC-06', t: 'Compromised cloud admin switches off audit logging', who: 'u-046 · cloud admin', src: 'Sign-in, IAM, CloudTrail', exp: 'CRITICAL 100', steps: ['6 MFA pushes, then a login from a city 1,400 km away', 'Emergency role assumed', 'StopLogging on CloudTrail: instant 100'] },
  { id: 'SC-07', t: 'Marketing reads KYC of customers who consented only to loan processing', who: 'u-037 · marketing user', src: 'Loan system, consent ledger', exp: 'HIGH 70', steps: ['40 customers read for marketing', 'Consent ledger allows loan processing only', 'Customers not assigned to this user'] },
  { id: 'SC-08', t: 'Bank account changed, then ₹4.8 lakh disbursed to it', who: 'u-032 · collections agent', src: 'Loan system', exp: 'HIGH 65', steps: ['Borrower bank account changed from a new device', '₹4.8 lakh disbursed to that account at 01:40, within 24 h'] },
  { id: 'SC-09', t: 'KYC bucket made public by mistake', who: 'AWS account · IT change', src: 'AWS Config', exp: 'MEDIUM 45', steps: ['Config rule s3-bucket-public-read-prohibited turns NON_COMPLIANT on the KYC bucket'] },
];

const DASHBOARD_URL = process.env.NEXT_PUBLIC_DASHBOARD_URL ?? 'http://localhost:3000';

export default function Simulator() {
  const [busy, setBusy] = useState<string | null>(null), [log, setLog] = useState<{ at: string; msg: string; bad?: boolean }[]>([]);
  const add = (msg: string, bad?: boolean) => setLog((l) => [{ at: new Date().toLocaleTimeString('en-GB'), msg, bad }, ...l]);
  const call = async (key: string, body: Parameters<typeof api.simulate>[0], okMsg: (r: SimulateResult) => string) => {
    if (busy) return; setBusy(key);
    try { add(okMsg(await api.simulate(body))); } catch (e) { add(`${key}: ${e instanceof Error ? e.message : String(e)}`, true); }
    setBusy(null);
  };
  return (
    <div className="grid g-7-5">
      <div>
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="muted">Each scenario is replayed with timestamps rewritten to now and sent into the live detection pipeline. Detection, containment and the AI explanation then run for real. Watch the alert appear in the <a href={DASHBOARD_URL} target="_blank" rel="noreferrer" style={{ color: '#60a5fa' }}>FinShield dashboard ↗</a>.</div></div>
        <div className="grid g2">
          {SCENARIOS.map((s) => (
            <div key={s.id} className="card sc-card" style={s.hero ? { borderColor: '#fdba74' } : undefined}>
              <div className="row"><span className="mono dim">{s.id}</span><b style={{ flex: 1 }}>{s.t}</b></div>
              <div className="dim" style={{ fontSize: 12 }}>👤 {s.who}<br />📡 {s.src}</div>
              <ul style={{ margin: 0, paddingLeft: 18, color: '#cfd7e8', fontSize: 12.5 }}>{s.steps.map((x) => <li key={x}>{x}</li>)}</ul>
              <div className="row" style={{ marginTop: 'auto' }}><span className="muted" style={{ fontSize: 12 }}>Expected</span><Pill sev={s.exp.split(' ')[0]}>{s.exp}</Pill>{s.hero && <span className="pill High">Mandated demo</span>}<span className="sp" />
                <button className={`btn ${s.hero ? 'hot' : 'primary'}`} disabled={!!busy} onClick={() => call(s.id, { scenario_id: s.id }, (r) => `${s.id} accepted, ${r.events_sent} events sent`)}>{busy === s.id ? 'Sending…' : '▶ Run'}</button></div>
            </div>))}</div>
      </div>
      <div>
        <div className="card"><h3>Environment</h3>
          <div className="row wrap">
            <button className="btn" disabled={!!busy} onClick={() => confirm('Clear alerts and counters for scenario users?') && call('reset', { reset: true }, () => 'Environment reset')}>↺ Reset environment</button>
            <button className="btn" disabled={!!busy} onClick={() => call('guardduty', { guardduty_sample: true }, () => 'GuardDuty sample findings requested')}>◆ GuardDuty sample findings</button></div></div>
        <div className="card" style={{ marginTop: 16 }}><h3>Requests</h3>
          <div style={{ maxHeight: 420, overflow: 'auto', fontSize: 12.5 }}>
            {log.length ? log.map((l, i) => <div key={i} style={{ padding: '6px 2px', borderBottom: '1px dashed #1a2643', color: l.bad ? '#fda4af' : undefined }}><span className="mono dim">{l.at}</span> {l.msg}</div>) : <div className="muted">Nothing sent yet.</div>}</div></div>
      </div>
    </div>
  );
}
