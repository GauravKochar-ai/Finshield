'use client';
import { useState } from 'react';
import { api, type AccuracyResult } from '@/lib/api';
import { useLoad } from '@/lib/hooks';
import { Ring } from '@/components/charts';
import { Pill } from '@/components/ui';
import { fmt, incidentType, ts } from '@/lib/format';

export default function Accuracy() {
  const last = useLoad<AccuracyResult | null>(() => api.getAccuracy().catch(() => null), []);
  const [run, setRun] = useState<AccuracyResult | null>(null), [busy, setBusy] = useState(false), [err, setErr] = useState('');
  const go = async () => { setBusy(true); setErr(''); try { setRun(await api.runAccuracy()); } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } setBusy(false); };
  const a = run ?? last.data;
  return (
    <>
      <div className="card"><div className="row wrap"><div><div style={{ fontSize: 16, fontWeight: 700 }}>Replay every scenario and 7 normal days on a clean copy</div>
        <div className="muted" style={{ fontSize: 12.5, marginTop: 3 }}>Compares each result with its expected level. Numbers are measured, not claimed.{a ? ` Last run ${ts(a.ran_at)}.` : ''}</div></div>
        <span className="sp" /><button className="btn primary" disabled={busy} onClick={go}>{busy ? 'Running…' : '▶ Run accuracy test'}</button></div>
        {err && <div className="err" style={{ marginTop: 8 }}>{err}</div>}</div>
      {a && <>
        <div className="grid g4" style={{ marginTop: 16 }}>
          <div className="card"><h3>Scenarios correct</h3><Ring v={a.passed} max={a.total} color={a.passed === a.total ? '#34d399' : '#f43f5e'} size={100} label={`${a.passed}/${a.total}`} /></div>
          <div className="card"><h3>False alerts</h3><div className="kpi" style={{ color: a.false_alerts_normal_days ? '#fda4af' : '#34d399' }}>{a.false_alerts_normal_days}<small>on 7 normal days</small></div></div>
          <div className="card"><h3>Slowest time to alert</h3><div className="kpi">{fmt(Math.max(0, ...a.rows.map((r) => r.time_to_alert_ms ?? 0)) / 1000)} s<small>from event to alert</small></div></div>
          <div className="card"><h3>Run</h3><div className="kpi" style={{ fontSize: 18 }}>{a.run_id}<small>{ts(a.ran_at)}</small></div></div></div>
        <div className="card" style={{ marginTop: 16 }}><table><thead><tr><th>Scenario</th><th>Expected</th><th>Result</th><th>Expected score</th><th>Score</th><th>Time to alert</th><th /></tr></thead><tbody>
          {a.rows.map((r) => <tr key={r.scenario_id}><td><b>{incidentType(r.scenario_id)}</b> <span className="dim mono">{r.scenario_id}</span></td>
            <td><Pill sev={r.expected_level} /></td><td><Pill sev={r.actual_level} /></td><td>{r.expected_score}</td><td><b>{r.actual_score}</b></td>
            <td className="mono dim">{r.time_to_alert_ms != null ? `${(r.time_to_alert_ms / 1000).toFixed(1)} s` : '—'}</td><td style={{ fontSize: 16 }}>{r.pass ? '✅' : '❌'}</td></tr>)}</tbody></table></div></>}
    </>
  );
}
