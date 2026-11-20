'use client';
import Link from 'next/link';
import { Suspense, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { api, can, type Alert, type AskResult } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useLoad } from '@/lib/hooks';
import { useAlerts } from '@/components/Shell';
import { AlertTable } from '@/components/AlertTable';
import { EvidenceChain } from '@/components/EvidenceChain';
import { Ring } from '@/components/charts';
import { Av, Empty, ErrorCard, Loading, Pill, SevBar, sevColor } from '@/components/ui';
import { actionName, alertType, bytes, collapseEvents, fmt, hm, label, runText, signalText, ts, SEV_COLOR } from '@/lib/format';
import { isUnmapped, systemName, useDeidentify } from '@/lib/people';

function Incidents() {
  const { alerts, error } = useAlerts();
  const router = useRouter();
  const sel = useSearchParams().get('id');
  if (error && !alerts) return <ErrorCard message={error} />;
  if (!alerts) return <Loading />;
  if (!alerts.length) return <Empty icon="🛡️">No incidents. FinShield is watching FinLend systems.</Empty>;
  const id = alerts.find((a) => a.alert_id === sel)?.alert_id ?? alerts[0].alert_id;
  return (
    <>
      <AlertTable alerts={alerts} selected={id} onSelect={(x) => router.replace(`/incidents/?id=${x}`)} />
      <div style={{ marginTop: 16 }}><Detail key={id} id={id} /></div>
    </>
  );
}

function Detail({ id }: { id: string }) {
  const { session } = useAuth();
  const groups = session!.groups;
  const { reload: reloadList } = useAlerts();
  const alert = useLoad(() => api.getAlert(id), [id], 2500);
  const timeline = useLoad(() => api.getAlertTimeline(id), [id], 5000);
  const rules = useLoad(() => api.getRules(), [], 0);
  const a = alert.data;
  const user = useLoad(() => (a && !isUnmapped(a.user_id) ? api.getUser(a.user_id).catch(() => null) : Promise.resolve(null)), [a?.user_id]);
  const deid = useDeidentify(a ? [a.user_id] : []);
  if (alert.error && !a) return <ErrorCard message={alert.error} />;
  if (!a) return <Loading />;

  const ai = a.ai;
  const s1 = a.signals.find((s) => s.code === 'S1'), s4 = a.signals.find((s) => s.code === 'S4');
  const ratio = s1 ? Number(s1.facts.ratio) : null;
  const sent = s4 ? Number(s4.facts.bytes) : 0;
  const st = a.status;
  const approved = ['LOCKED', 'RELEASED'].includes(st);
  const done: Record<string, boolean> = {
    detected: true, explained: a.ai_status !== 'PENDING', contained: a.containment.length > 0,
    approval: !['OPEN', 'CONTAINED', 'AWAITING_APPROVAL'].includes(st), closed: ['LOCKED', 'RELEASED', 'CLOSED'].includes(st),
  };
  const steps: [string, string, string][] = [
    ['detected', 'Detected', hm(a.detected_at)],
    ['explained', 'AI investigated', a.ai_status === 'PENDING' ? '…' : 'complete'],
    ['contained', 'Contained', a.containment.length ? 'automatic' : '—'],
    ['approval', 'Security Head', st === 'AWAITING_APPROVAL' ? 'pending' : approved ? 'approved' : '—'],
    ['closed', 'Closed', label(st)],
  ];
  const firstOpen = steps.findIndex((s) => !done[s[0]]);
  const runs = collapseEvents(timeline.data ?? []);
  const KEYS = ['UPLOAD_EXTERNAL', 'ASSUME_ROLE', 'LOGGING_CHANGE', 'CONFIG_NONCOMPLIANT', 'GUARDDUTY_FINDING'];
  const system = isUnmapped(a.user_id);
  const displayName = system ? systemName(a.user_id) : user.data?.name_pseudo ?? a.user_id;
  const say = (t: string) => deid(t, a.user_id, displayName);

  return (
    <>
      <div className={`banner ${a.severity[0] + a.severity.slice(1).toLowerCase()}`}>
        <div>
          <div className="row wrap"><Pill sev={a.severity}>● {a.severity}</Pill><span className="pill cat">{alertType(a)}</span><span className="mono dim">{a.alert_id}</span></div>
          <h2>{ai ? say(ai.headline) : alertType(a)}</h2>
          <div className="row wrap muted" style={{ gap: 16, fontSize: 13 }}>
            <span className="who"><Av name={displayName} size={26} /><b style={{ color: 'var(--ink)' }}>{displayName}</b>{system ? ' · system role, not linked to a person' : user.data ? <> · {user.data.role} · {user.data.team}</> : null}</span>
            <span>Detected {ts(a.detected_at)} IST</span><span>Activity from {hm(a.window_start)}</span></div>
          <div className="steps" style={{ marginTop: 20 }}>
            {steps.map((s, i) => <div key={s[0]} className={`step ${done[s[0]] ? 'done' : i === firstOpen ? 'now' : ''}`}><div className="c">{done[s[0]] ? '✓' : i + 1}</div><b>{s[1]}</b>{s[2]}</div>)}</div></div>
        <div style={{ textAlign: 'center' }}><Ring v={a.score} max={100} color={SEV_COLOR[a.severity]} size={136} label={a.score} sub="risk score" /></div>
      </div>

      <div className="grid g4" style={{ marginTop: 16 }}>
        <div className="card tile"><div className="v" style={{ color: a.customers_affected ? '#fda4af' : undefined }}>{fmt(a.customers_affected)}</div><div className="l">customers affected</div></div>
        <div className="card tile"><div className="v">{fmt((timeline.data ?? []).length || a.event_ids.length)}</div><div className="l">events · {a.data_classes.filter((d) => d !== 'NONE').join(', ') || 'no customer data'}</div></div>
        <div className="card tile"><div className="v">{s4 ? bytes(sent) : '—'}</div><div className="l">{s4 ? `sent to ${s4.facts.destination}` : 'no data sent outside'}</div></div>
        <div className="card tile"><div className="v">{ratio ? `${fmt(ratio)}×` : '—'}</div><div className="l">{s1 ? `${fmt(s1.facts.downloads_15m as number)} downloads / 15 min vs usual ${fmt(s1.facts.baseline_p95 as number)}` : 'no volume spike'}</div></div>
      </div>

      <div className="grid g-5-7" style={{ marginTop: 16 }}>
        <div className="card"><h3>Why it fired <span className="r">{a.signals.length} warning signs</span></h3>
          {a.signals.map((s) => (
            <div key={s.code} className="sig"><div><div className="n">{rules.data?.signals[s.code]?.name as string ?? s.code}</div><div className="d">{signalText(s.code, s.facts)}</div></div>
              <SevBar pct={(s.points / 40) * 100} color="linear-gradient(90deg,#fb923c,#f43f5e)" /><b style={{ textAlign: 'right' }}>+{s.points}</b></div>
          ))}
          {a.exceptions_applied.length > 0 && <p className="muted">Approved work {a.exceptions_applied.join(', ')} applied, score capped.</p>}
          {runs.length > 0 && <><h3 style={{ marginTop: 16 }}>What happened</h3>
            <div className="tl" style={{ maxHeight: 360, overflow: 'auto' }}>{runs.slice(0, 40).map((r, i) => (
              <div key={i} className={`tli ${KEYS.includes(r.action) ? 'bad' : ''}`}><div className="t">{hm(r.first)}{r.n > 1 && hm(r.last) !== hm(r.first) ? `–${hm(r.last)}` : ''}</div>
                <div>{runText(r)}</div></div>
            ))}</div></>}
        </div>
        <AiCard alert={a} groups={groups} say={say} />
      </div>

      <div className="grid g2" style={{ marginTop: 16 }}>
        <div className="card"><h3>Automated response</h3>
          {a.containment.length ? a.containment.map((x, i) => (
            <div key={i} className="row" style={{ padding: '9px 0', borderBottom: '1px solid #1a2643' }}>
              <span style={{ color: x.result === 'OK' ? '#34d399' : '#fda4af' }}>{x.result === 'OK' ? '✓' : '✗'}</span><span style={{ flex: 1 }}>{actionName(x.action)}</span>
              <span className={`pill ${x.mode === 'LIVE' ? 'real' : 'simulated'}`}>{x.mode === 'LIVE' ? 'enforced' : 'simulated'}</span><span className="mono dim">{hm(x.at)}</span></div>
          )) : <div className="muted">Containment starts automatically for Critical incidents.</div>}</div>
        <SignOff alert={a} groups={groups} onChange={() => { alert.reload(); reloadList(); }} />
      </div>

      {user.data && (
        <div className="card" style={{ marginTop: 16 }}><h3>Normal behaviour for {displayName} <span className="r">learned from past activity</span></h3>
          <div className="grid g4" style={{ gap: 14, fontSize: 12.5 }}>
            <div><b>{fmt(user.data.baseline.p95_15min)}</b><div className="muted">KYC downloads in a busy 15 min</div></div>
            <div><b>{fmt(user.data.baseline.avg_daily)}</b><div className="muted">KYC downloads on a normal day</div></div>
            <div><b>{user.data.baseline.usual_hours}</b><div className="muted">working hours{user.data.baseline.cities.length ? ` · ${user.data.baseline.cities.join(', ')}` : ''}</div></div>
            <div><b>{user.data.baseline.devices.length}</b><div className="muted">known device{user.data.baseline.devices.length === 1 ? '' : 's'}</div></div></div>
          <div className="dim" style={{ fontSize: 12, marginTop: 10 }}>The warning signs above are measured against these numbers.</div></div>
      )}
      <EvidenceChain alertId={id} canTamper={can.admin(groups)} />
    </>
  );
}

function AiCard({ alert: a, groups, say }: { alert: Alert; groups: Parameters<typeof can.ask>[0]; say: (t: string) => string }) {
  const ai = a.ai;
  const [q, setQ] = useState(''), [ans, setAns] = useState<AskResult | null>(null), [busy, setBusy] = useState(false), [err, setErr] = useState('');
  const ask = async () => {
    if (!q.trim()) return; setBusy(true); setErr('');
    try { setAns(await api.askFinShield(a.alert_id, q)); } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  };
  return (
    <div className="card ai"><h3><svg width="15" height="15" viewBox="0 0 24 24" fill="#a78bfa"><path d="M12 2l2.4 6.6L21 11l-6.6 2.4L12 20l-2.4-6.6L3 11l6.6-2.4z" /></svg> AI investigation</h3>
      {ai ? <>
        <div className="head">{say(ai.headline)}</div><p style={{ color: '#cfd7e8', lineHeight: 1.55 }}>{say(ai.summary)}</p>
        {ai.why_unusual.length > 0 && <><b>Why it is unusual</b><ul>{ai.why_unusual.map((x) => <li key={x}>{say(x)}</li>)}</ul></>}
        {ai.root_cause_hypotheses.length > 0 && <div style={{ background: 'rgba(167,139,250,.08)', border: '1px solid rgba(167,139,250,.25)', borderRadius: 10, padding: '10px 12px', margin: '10px 0' }}>
          <b>Likely root cause</b><div style={{ color: '#cfd7e8', marginTop: 3 }}>{ai.root_cause_hypotheses.map(say).join(' · ')}</div></div>}
        <div className="grid g2" style={{ gap: 14 }}>
          <div><b>Regulations engaged</b><ul>{ai.rules_affected.map((r) => <li key={r.regulation + r.clause}>{r.regulation} <span className="dim">· {r.clause}</span></li>)}</ul></div>
          <div><b>Recommended next steps</b><ul>{ai.recommended_actions.map((x) => <li key={x}>{say(x)}</li>)}</ul>
            </div></div>
        <div className="muted" style={{ fontSize: 12.5 }}>Confidence <b style={{ color: 'var(--ink)' }}>{ai.confidence}</b> · {say(ai.confidence_reason)}</div>
      </> : <div className="muted">Investigating…</div>}
      {can.ask(groups) && (
        <div style={{ marginTop: 14, borderTop: '1px solid var(--line)', paddingTop: 12 }}>
          <div className="row"><input className="field" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && ask()} placeholder="Ask FinShield about this incident…" />
            <button className="btn primary" disabled={busy} onClick={ask}>{busy ? '…' : 'Ask'}</button></div>
          {err && <div className="err" style={{ marginTop: 8 }}>{err}</div>}
          {ans && <div style={{ marginTop: 10, fontSize: 13, color: '#cfd7e8', lineHeight: 1.55 }}>
            {ans.ai_status && <span className="pill" style={{ marginRight: 8, fontSize: 11, background: ans.ai_status === 'OK' ? 'rgba(167,139,250,.15)' : 'rgba(148,163,184,.15)', color: ans.ai_status === 'OK' ? '#a78bfa' : '#94a3b8' }}>{ans.ai_status === 'OK' ? 'AI' : 'Rule-based'}</span>}
            {say(ans.answer)}</div>}
        </div>)}
    </div>
  );
}

function SignOff({ alert: a, groups, onChange }: { alert: Alert; groups: Parameters<typeof can.ask>[0]; onChange: () => void }) {
  const [reason, setReason] = useState(''), [busy, setBusy] = useState(false), [err, setErr] = useState('');
  const act = async (fn: () => Promise<unknown>) => { setBusy(true); setErr(''); try { await fn(); onChange(); } catch (e) { setErr(e instanceof Error ? e.message : String(e)); } setBusy(false); };
  const pending = a.status === 'AWAITING_APPROVAL';
  return (
    <div className="card"><h3>Human sign-off</h3>
      <div style={{ fontSize: 15, fontWeight: 700, marginBottom: 6 }}>{pending ? 'Lock down the account' : label(a.status)}</div>
      <div className="muted">Status <b style={{ color: a.status === 'LOCKED' ? '#34d399' : pending ? '#fdba74' : 'var(--ink)' }}>{label(a.status)}</b></div>
      {pending && can.decide(groups) && <input className="field" style={{ marginTop: 12 }} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason (kept in the evidence trail)" />}
      <div className="row" style={{ marginTop: 14 }}>
        {pending && can.decide(groups) && <>
          <button className="btn ok" disabled={busy} onClick={() => act(() => api.decideAlert(a.alert_id, 'APPROVE', reason || 'Approved'))}>✓ Approve</button>
          <button className="btn" disabled={busy} onClick={() => act(() => api.decideAlert(a.alert_id, 'REJECT', reason || 'Rejected'))}>Reject</button></>}
        {pending && !can.decide(groups) && <span className="muted">Waiting for the Security Head or Compliance Head.</span>}
        {a.status === 'LOCKED' && can.release(groups) && <button className="btn hot" disabled={busy} onClick={() => act(() => api.releaseAlert(a.alert_id))}>Release access</button>}
        <span className="sp" />
        <Link className="btn" href="/deadlines/">Regulator deadlines →</Link></div>
      {err && <div className="err" style={{ marginTop: 8 }}>{err}</div>}</div>
  );
}

export default function Page() {
  return <Suspense fallback={<Loading />}><Incidents /></Suspense>;
}
