'use client';
import { useState } from 'react';
import { api, type SimulateResult } from '@/lib/api';
import { Pill } from '@/components/ui';

const SCENARIOS: { id: string; t: string; who: string; src: string; exp: string; hero?: boolean; steps: string[] }[] = [
  { id: 'SC-01', hero: true, t: 'Ops admin bulk-exports KYC files at night and uploads outside', who: 'u-017 · ops admin', src: 'Sign-in, IAM, KYC store, CloudTrail', exp: 'CRITICAL', steps: ['23:40 emergency role from a new device and second city', '212 KYC files in 15 min (106× usual)', 'Upload to an external share'] },
  { id: 'SC-01b', t: 'Same as SC-01 without the upload', who: 'u-017 · ops admin', src: 'Sign-in, IAM, KYC store', exp: 'CRITICAL', steps: ['Detection fires on the export itself, before data leaves'] },
  { id: 'SC-06', t: 'Compromised cloud admin', who: 'cloud admin', src: 'Sign-in, CloudTrail', exp: 'CRITICAL', steps: ['6 MFA pushes, login from a city 1,400 km away', 'Emergency role, then StopLogging'] },
  { id: 'SC-04', t: 'Collections agent opens 120 unassigned customers', who: 'collections agent', src: 'Partner portal', exp: 'HIGH', steps: ['120 customers in 15 min, none assigned'] },
  { id: 'SC-07', t: 'Marketing reads KYC of customers who consented only to loan processing', who: 'marketing user', src: 'Loan system, consent records', exp: 'HIGH', steps: ['40 customers, purpose mismatch'] },
  { id: 'SC-08', t: 'Agent changes bank account then disburses ₹4.8 lakh', who: 'collections agent', src: 'Loan system', exp: 'HIGH', steps: ['New device, bank account change', '01:40 disbursement'] },
  { id: 'SC-09', t: 'KYC bucket made public', who: 'IT engineer', src: 'AWS Config', exp: 'MEDIUM', steps: ['Config rule s3-bucket-public-read-prohibited turns NON_COMPLIANT'] },
  { id: 'SC-10', t: 'Auditor exceeds a 100-file ticket by 50%', who: 'auditor', src: 'KYC store', exp: 'MEDIUM', steps: ['150 files downloaded, ticket exceeded by more than 20%'] },
  { id: 'SC-02', t: 'Nightly KYC registry upload (approved job)', who: 'service account', src: 'Batch job', exp: 'LOGGED', steps: ['Inside job window, capped by approval → no false alarm'] },
  { id: 'SC-03', t: 'Auditor pulls 90 files under a 100-file ticket', who: 'auditor', src: 'KYC store', exp: 'LOGGED', steps: ['Approved ticket → no false alarm'] },
  { id: 'SC-05', t: 'One late-night download of 15 files', who: 'credit analyst', src: 'KYC store', exp: 'LOGGED', steps: ['Slightly unusual, below alert level → no over-alerting'] },
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
              <div className="row" style={{ marginTop: 'auto' }}><span className="muted" style={{ fontSize: 12 }}>Expected</span><Pill sev={s.exp} />{s.hero && <span className="pill High">Mandated demo</span>}<span className="sp" />
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
