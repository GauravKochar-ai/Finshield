'use client';
import Link from 'next/link';
import { useState } from 'react';
import { api, can } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useLoad } from '@/lib/hooks';
import { useAlerts } from '@/components/Shell';
import { Empty, ErrorCard, Loading, Pill } from '@/components/ui';
import { hm, incidentType, ts, userLabel } from '@/lib/format';

export default function Approvals() {
  const { session } = useAuth();
  const groups = session!.groups;
  const { alerts, error, reload } = useAlerts();
  const exceptions = useLoad(() => (can.approvals(groups) ? api.listApprovals() : Promise.resolve([])), [groups.join()], 10000);
  const [err, setErr] = useState('');
  if (error && !alerts) return <ErrorCard message={error} />;
  if (!alerts) return <Loading />;
  const pending = alerts.filter((a) => a.status === 'AWAITING_APPROVAL');
  const decide = async (id: string, d: 'APPROVE' | 'REJECT') => {
    setErr('');
    try { await api.decideAlert(id, d, d === 'APPROVE' ? 'Approved from approvals queue' : 'Rejected from approvals queue'); reload(); }
    catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  };
  return (
    <>
      {err && <div className="err">{err}</div>}
      {pending.length === 0 ? <Empty icon="✅">Nothing is waiting for approval.</Empty> : pending.map((a) => (
        <div key={a.alert_id} className="card" style={{ marginBottom: 14 }}>
          <div className="row wrap"><Pill sev={a.severity} /><span className="pill cat">{incidentType(a.scenario_id)}</span><span className="mono dim">{a.alert_id}</span></div>
          <div style={{ fontSize: 17, fontWeight: 700, margin: '10px 0 4px' }}>Lock down account {userLabel(a.user_id)}</div>
          <div className="muted">{a.ai?.headline ?? ''} · {userLabel(a.user_id)} · risk {a.score} · detected {hm(a.detected_at)}</div>
          <div className="row" style={{ marginTop: 14 }}>
            {can.decide(groups) ? <><button className="btn ok" onClick={() => decide(a.alert_id, 'APPROVE')}>✓ Approve</button><button className="btn" onClick={() => decide(a.alert_id, 'REJECT')}>Reject</button></>
              : <span className="muted">Only the Security Head or Compliance Head can approve.</span>}
            <span className="sp" /><Link className="btn" href={`/incidents/?id=${a.alert_id}`}>Open incident →</Link></div>
        </div>
      ))}
      {can.approvals(groups) && (
        <div className="card" style={{ marginTop: 16 }}><h3>Pre-approved exceptions <span className="r">tickets and scheduled jobs that are allowed</span></h3>
          {(exceptions.data ?? []).length ? <table><thead><tr><th>ID</th><th>Type</th><th>Subject</th><th>Max files</th><th>Class</th><th>Valid</th></tr></thead><tbody>
            {exceptions.data!.map((x) => <tr key={x.approval_id}><td className="mono">{x.approval_id}</td><td>{x.type}</td><td>{x.subject_id}{x.job_id ? ` · ${x.job_id}` : ''}</td><td>{x.max_files ?? '—'}</td><td>{x.data_class ?? '—'}</td><td className="mono dim">{ts(x.valid_from)} → {ts(x.valid_to)}</td></tr>)}</tbody></table>
            : <div className="muted">No standing approvals.</div>}</div>)}
    </>
  );
}
