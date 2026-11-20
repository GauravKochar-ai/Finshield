'use client';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api, type Alert, type FinShieldEvent } from '@/lib/api';
import { useLoad, useNow } from '@/lib/hooks';
import { useAlerts } from '@/components/Shell';
import { AreaChart, Donut, HBars, Ring } from '@/components/charts';
import { ErrorCard, Loading, Pill, SevBar, sevColor } from '@/components/ui';
import { WhoCell } from '@/components/WhoCell';
import { useWho } from '@/lib/people';
import { DEADLINE_HOURS, DEADLINE_LABEL, SEV_COLOR, alertType, collapseEvents, countdown, fmt, groupChecks, hm, label, runText } from '@/lib/format';

const SUSPICIOUS = ['UPLOAD_EXTERNAL', 'ASSUME_ROLE', 'LOGGING_CHANGE', 'CONFIG_NONCOMPLIANT', 'GUARDDUTY_FINDING', 'BANK_ACCOUNT_CHANGE', 'DISBURSE'];
const ICON: Record<string, [string, string]> = {
  DOWNLOAD: ['⇣', '#60a5fa'], PRESIGN: ['⇣', '#60a5fa'], KYC_FILE_UPLOADED: ['⇡', '#2dd4bf'], VIEW: ['◉', '#2dd4bf'], LOGIN: ['⏻', '#a78bfa'],
  MFA_PUSH: ['✱', '#a78bfa'], ASSUME_ROLE: ['⚑', '#fb923c'], UPLOAD_EXTERNAL: ['⇡', '#f43f5e'], LOGGING_CHANGE: ['⚠', '#f43f5e'],
  CONFIG_NONCOMPLIANT: ['⚙', '#f43f5e'], GUARDDUTY_FINDING: ['◆', '#f43f5e'],
};

const SOURCE: Record<string, string> = { simulator: 'FinLend apps', app: 'FinLend apps', cloudtrail: 'Cloud activity', config: 'Cloud checks', guardduty: 'Threat detection' };

export default function Overview() {
  const { alerts, error } = useAlerts();
  const router = useRouter();
  const posture = useLoad(() => api.getPosture(), [], 5000);
  const privacy = useLoad(() => api.getPrivacy(), [], 15000);
  const compliance = useLoad(() => api.getCompliance(), [], 30000);
  const latest = alerts?.[0];
  const feed = useLoad<FinShieldEvent[]>(() => (latest ? api.getAlertTimeline(latest.alert_id) : Promise.resolve([])), [latest?.alert_id], 5000);
  const now = useNow(1000);
  const who = useWho((alerts ?? []).map((a) => a.user_id));

  if (error && !alerts) return <ErrorCard message={error} />;
  const p = posture.data;
  if (!alerts || !p) return <Loading />;

  const pc = p.posture_score >= 80 ? '#34d399' : p.posture_score >= 50 ? '#facc15' : '#f43f5e';
  const open = alerts.filter((a) => !['CLOSED', 'RELEASED'].includes(a.status));
  const sev = { CRITICAL: 0, HIGH: 0, MEDIUM: 0 } as Record<string, number>;
  open.forEach((a) => (sev[a.severity] += 1));
  const tot = open.length;
  const exposed = open.reduce((n, a) => n + a.customers_affected, 0);
  const cs = compliance.data ?? [];
  const checks = groupChecks(p.config_results);
  const ctlMet = cs.filter((c) => c.status === 'IN_PLACE').length + checks.filter((c) => !c.fail.length && !c.unknown).length;
  const ctlGap = cs.filter((c) => c.status === 'GAP' || c.status === 'UNKNOWN').length + checks.filter((c) => !c.fail.length && c.unknown).length;
  const ctlFail = checks.filter((c) => c.fail.length).length;

  const events = feed.data ?? [];
  const times = events.map((e) => new Date(e.ts).getTime());
  const badTimes = events.filter((e) => SUSPICIOUS.includes(e.action)).map((e) => new Date(e.ts).getTime());
  const runs = collapseEvents(events).reverse();
  const sources = [...new Set(events.map((e) => e.source))];

  const byUser = new Map<string, Alert>();
  open.forEach((a) => { const o = byUser.get(a.user_id); if (!o || a.score > o.score) byUser.set(a.user_id, a); });
  const risky = [...byUser.values()].sort((a, b) => b.score - a.score).slice(0, 5);
  const byType = new Map<string, number>();
  open.forEach((a) => byType.set(alertType(a), (byType.get(alertType(a)) ?? 0) + 1));

  return (
    <>
      {/* ---- KPIs ---- */}
      <div className="grid g4">
        <div className="card"><h3>Security posture</h3>
          <div className="row" style={{ gap: 16 }}><Ring v={p.posture_score} max={100} color={pc} size={104} label={p.posture_score} sub="/ 100" />
            <div><div style={{ fontWeight: 700, color: pc }}>{p.posture_score >= 80 ? 'Healthy' : p.posture_score >= 50 ? 'Needs attention' : 'At risk'}</div>
              <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>Lowered by open incidents and failing checks.</div></div></div></div>
        <div className="card"><h3>Open incidents</h3><div className="kpi">{tot}</div>
          {(['CRITICAL', 'HIGH', 'MEDIUM'] as const).map((s) => (
            <div key={s} style={{ marginTop: 8 }}><div className="row" style={{ justifyContent: 'space-between', fontSize: 12.5 }}><span><span className="dot" style={{ background: SEV_COLOR[s] }} /> {label(s)}</span><b>{sev[s]}</b></div>
              <div style={{ marginTop: 4 }}><SevBar pct={tot ? (sev[s] / tot) * 100 : 0} color={SEV_COLOR[s]} /></div></div>))}</div>
        <div className="card"><h3>Privacy risk</h3>
          <div className="kpi" style={{ color: exposed ? '#fda4af' : 'inherit' }}>{fmt(exposed)}<small>customers affected by open incidents</small></div>
          <div className="grid g2" style={{ gap: 10, marginTop: 12, fontSize: 12.5 }}>
            <div><b>{fmt(p.consent_risks.purpose_mismatches)}</b><div className="muted">purpose mismatches</div></div>
            <div><b>{fmt(p.consent_risks.withdrawn_consents_accessed)}</b><div className="muted">withdrawn consents used</div></div>
            <div><b>{fmt(privacy.data?.unmasked_aadhaar_files.length ?? 0)}</b><div className="muted">unmasked Aadhaar files</div></div>
            <div><b>{fmt(privacy.data?.consent_risks.length ?? 0)}</b><div className="muted">consent risks</div></div></div></div>
        <Link href="/compliance/" className="card" style={{ textDecoration: 'none' }}><h3>Compliance</h3>
          <div className="row" style={{ gap: 16 }}>
            <Donut size={104} parts={[{ v: ctlMet, c: '#34d399' }, { v: ctlGap, c: '#facc15' }, { v: ctlFail, c: '#f43f5e' }]} />
            <div style={{ fontSize: 12.5, lineHeight: 1.9 }}>
              <div><span className="dot" style={{ background: '#34d399' }} /> {ctlMet} met</div>
              <div><span className="dot" style={{ background: '#facc15' }} /> {ctlGap} to review</div>
              <div><span className="dot" style={{ background: '#f43f5e' }} /> {ctlFail} failing</div></div></div></Link>
      </div>

      {/* ---- incidents ---- */}
      <div className="grid g-7-5 at" style={{ marginTop: 16 }}>
        <div className="card"><h3>Open incidents <span className="r">{open.length} open</span></h3>
          {open.length ? (
            <table className="fixed"><colgroup><col style={{ width: 100 }} /><col style={{ width: '36%' }} /><col /><col style={{ width: 56 }} /><col style={{ width: 96 }} /></colgroup>
              <thead><tr><th>Severity</th><th>Incident</th><th>Identity</th><th>Risk</th><th>Status</th></tr></thead><tbody>
                {open.map((a) => (
                  <tr key={a.alert_id} className="click" onClick={() => router.push(`/incidents/?id=${a.alert_id}`)}>
                    <td><Pill sev={a.severity} /></td>
                    <td><div style={{ fontWeight: 600 }}>{alertType(a)}</div><div className="dim" style={{ fontSize: 12 }}>{a.alert_id} · {hm(a.detected_at)}</div></td>
                    <td><WhoCell who={who(a.user_id)} /></td>
                    <td><b style={{ color: sevColor(a.severity) }}>{a.score}</b></td>
                    <td className="muted" style={{ textTransform: 'capitalize' }}>{label(a.status)}</td></tr>))}
              </tbody></table>
          ) : <div className="empty"><div className="big">🛡️</div>All clear. FinLend systems are being monitored.</div>}
        </div>
        <div className="grid" style={{ gap: 16 }}>
          <div className="card"><h3>Riskiest identities</h3>
            {risky.length ? risky.map((a) => (
              <div key={a.user_id} className="row" style={{ padding: '6px 0' }}>
                <div style={{ flex: '0 0 55%', minWidth: 0 }}><WhoCell who={who(a.user_id)} /></div>
                <div style={{ flex: 1 }}><SevBar pct={a.score} color={sevColor(a.severity)} /></div><b style={{ width: 30, textAlign: 'right' }}>{a.score}</b></div>
            )) : <div className="muted">No risky activity.</div>}</div>
          <div className="card"><h3>Regulator deadlines</h3>
            {p.deadlines_due_soon.length ? p.deadlines_due_soon.map((d) => (
              <div key={d.alert_id + d.body} className="row" style={{ padding: '6px 0', fontSize: 12.5 }}>
                <span className="pill cat" style={{ minWidth: 64, justifyContent: 'center' }}>{d.body}</span>
                <span className="ellip muted" style={{ flex: 1 }}>{DEADLINE_LABEL[d.body]} · {d.alert_id}</span>
                <b className="mono">{countdown(d.due_at, DEADLINE_HOURS[d.body] ?? 6, now).txt}</b></div>
            )) : <div className="muted">No reports due.</div>}</div>
        </div>
      </div>

      {/* ---- activity + checks ---- */}
      <div className="grid g-7-5 at" style={{ marginTop: 16 }}>
        <div className="card">
          <h3>Latest incident activity <span className="r">{latest ? `${alertType(latest)} · ${fmt(events.length)} events` : ''}</span></h3>
          {events.length ? <>
            <AreaChart times={times} bad={badTimes} h={120} />
            <div className="row" style={{ gap: 14, fontSize: 12, margin: '8px 0 12px' }}>
              <span className="muted"><span className="dot" style={{ background: '#60a5fa' }} /> all events</span>
              <span className="muted"><span className="dot" style={{ background: '#f43f5e' }} /> suspicious</span><span className="sp" />
              {sources.map((s) => <span key={s} className="pill cat">{SOURCE[s] ?? label(s)}</span>)}</div>
            <div className="feed" style={{ maxHeight: 260 }}>
              {runs.slice(0, 30).map((r, i) => { const ic = ICON[r.action] ?? ['•', '#8e9ab5']; return (
                <div key={i} className={`fi ${SUSPICIOUS.includes(r.action) ? 'bad' : ''}`}><span className="t">{hm(r.first)}{r.n > 1 && r.last.slice(11, 16) !== r.first.slice(11, 16) ? `–${hm(r.last)}` : ''}</span>
                  <span className="ic" style={{ background: ic[1] + '22', color: ic[1] }}>{ic[0]}</span>
                  <span className="ellip"><b>{who(r.user_id).name}</b> <span className="act">{runText(r)}</span></span></div>); })}</div>
          </> : <div className="empty">No activity recorded for the latest incident.</div>}
        </div>
        <div className="grid" style={{ gap: 16 }}>
          <div className="card"><h3>Incidents by type</h3>
            {byType.size ? <HBars items={[...byType].map(([k, v]) => ({ k, v, c: 'linear-gradient(90deg,#fb923c,#f43f5e)' }))} /> : <div className="muted">No open incidents.</div>}</div>
          <Link href="/compliance/" className="card" style={{ textDecoration: 'none' }}><h3>Cloud security checks <span className="r">{p.config_results.length} resources checked</span></h3>
            {checks.length ? checks.map((c) => (
              <div key={c.name} className="row" style={{ padding: '7px 0', fontSize: 13, alignItems: 'flex-start' }}>
                <span className="dot" style={{ background: c.fail.length ? '#f43f5e' : c.unknown ? '#facc15' : '#34d399', marginTop: 6 }} />
                <div style={{ flex: 1 }}><div>{c.name}</div>
                  <div className="dim" style={{ fontSize: 12 }}>{c.fail.length ? `${c.fail.length} of ${c.total} ${c.unit} failing` : `${c.pass} of ${c.total} ${c.unit} passing`}</div></div>
                <b style={{ color: c.fail.length ? '#fda4af' : '#6ee7b7', fontSize: 12 }}>{c.fail.length ? 'Failing' : 'Passing'}</b></div>
            )) : <div className="muted">No checks reported yet.</div>}</Link>
        </div>
      </div>
    </>
  );
}
