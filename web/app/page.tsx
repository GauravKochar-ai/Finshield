'use client';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { api, type Alert, type FinShieldEvent } from '@/lib/api';
import { useLoad, useNow } from '@/lib/hooks';
import { useAlerts } from '@/components/Shell';
import { AreaChart, Donut, HBars, Ring } from '@/components/charts';
import { Av, ErrorCard, Pill, SevBar, sevColor } from '@/components/ui';
import { DEADLINE_HOURS, DEADLINE_LABEL, SEV_COLOR, checkName, incidentType, countdown, fmt, hms, label, userLabel } from '@/lib/format';

const BAD_ACTIONS = ['UPLOAD_EXTERNAL', 'ASSUME_ROLE', 'STOP_LOGGING', 'CONFIG_CHANGE', 'GUARDDUTY_FINDING', 'CHANGE_BANK_ACCOUNT'];
const ICON: Record<string, [string, string]> = {
  DOWNLOAD: ['⇣', '#60a5fa'], PRESIGN: ['⇣', '#60a5fa'], VIEW: ['◉', '#2dd4bf'], LOGIN: ['⏻', '#a78bfa'], MFA_PUSH: ['✱', '#a78bfa'],
  ASSUME_ROLE: ['⚑', '#fb923c'], UPLOAD_EXTERNAL: ['⇡', '#f43f5e'], CONFIG_CHANGE: ['⚙', '#f43f5e'], GUARDDUTY_FINDING: ['◆', '#f43f5e'],
};

export default function Overview() {
  const { alerts, error } = useAlerts();
  const posture = useLoad(() => api.getPosture(), [], 3000);
  const privacy = useLoad(() => api.getPrivacy(), [], 10000);
  const compliance = useLoad(() => api.getCompliance(), [], 30000);
  const latest = alerts?.[0]?.alert_id;
  const feed = useLoad<FinShieldEvent[]>(() => (latest ? api.getAlertTimeline(latest) : Promise.resolve([])), [latest], 5000);
  const now = useNow(1000);
  const router = useRouter();

  if (error && !alerts) return <ErrorCard message={error} />;
  const p = posture.data;
  if (!alerts || !p) return <div className="card"><div className="empty">Loading…</div></div>;

  const pc = p.posture_score >= 80 ? '#34d399' : p.posture_score >= 50 ? '#facc15' : '#f43f5e';
  const sev = p.alerts_by_severity;
  const tot = sev.CRITICAL + sev.HIGH + sev.MEDIUM;
  const exposed = alerts.reduce((a, x) => a + x.customers_affected, 0);
  const cs = compliance.data ?? [];
  const inPlace = cs.filter((c) => c.status === 'IN_PLACE').length, gap = cs.filter((c) => c.status === 'GAP').length;
  const cfgFail = p.config_results.filter((c) => c.status === 'NON_COMPLIANT').length;
  const cfgOk = p.config_results.filter((c) => c.status === 'COMPLIANT').length;
  const events = [...(feed.data ?? [])].sort((a, b) => b.ts.localeCompare(a.ts));
  const times = events.map((e) => new Date(e.ts).getTime());
  const badTimes = events.filter((e) => BAD_ACTIONS.includes(e.action)).map((e) => new Date(e.ts).getTime());

  const byUser = new Map<string, Alert>();
  alerts.forEach((a) => { const o = byUser.get(a.user_id); if (!o || a.score > o.score) byUser.set(a.user_id, a); });
  const risky = [...byUser.values()].sort((a, b) => b.score - a.score);
  const byScenario = new Map<string, number>();
  alerts.forEach((a) => byScenario.set(incidentType(a.scenario_id), (byScenario.get(incidentType(a.scenario_id)) ?? 0) + 1));

  return (
    <>
      <div className="grid g-dash">
        <div className="card"><h3>Security posture</h3>
          <div className="row" style={{ gap: 18 }}><Ring v={p.posture_score} max={100} color={pc} size={118} label={p.posture_score} sub="/ 100" />
            <div><div style={{ fontWeight: 700, color: pc }}>{p.posture_score >= 80 ? 'Healthy' : p.posture_score >= 50 ? 'Needs attention' : 'At risk'}</div>
              <div className="muted" style={{ fontSize: 12.5, marginTop: 4 }}>Open incidents and control gaps lower the score.</div></div></div></div>
        <div className="card"><h3>Active incidents</h3><div className="kpi">{tot}<small>open across all sources</small></div>
          {(['CRITICAL', 'HIGH', 'MEDIUM'] as const).map((s) => (
            <div key={s} style={{ marginTop: 9 }}><div className="row" style={{ justifyContent: 'space-between', fontSize: 12.5 }}><span><span className="dot" style={{ background: SEV_COLOR[s] }} /> {s[0] + s.slice(1).toLowerCase()}</span><b>{sev[s]}</b></div>
              <div style={{ marginTop: 4 }}><SevBar pct={tot ? (sev[s] / tot) * 100 : 0} color={SEV_COLOR[s]} /></div></div>
          ))}</div>
        <div className="card"><h3>Privacy risk</h3>
          <div className="kpi" style={{ color: exposed ? '#fda4af' : 'inherit' }}>{fmt(exposed)}<small>customers&apos; data exposed</small></div>
          <div className="grid g2" style={{ gap: 10, marginTop: 12, fontSize: 12.5 }}>
            <div><b>{fmt(p.consent_risks.purpose_mismatches)}</b><div className="muted">purpose mismatches</div></div>
            <div><b>{fmt(p.consent_risks.withdrawn_consents_accessed)}</b><div className="muted">withdrawn consents used</div></div>
            <div><b>{fmt(privacy.data?.unmasked_aadhaar_files.length)}</b><div className="muted">unmasked Aadhaar files</div></div>
            <div><b>{fmt(privacy.data?.consent_risks.length)}</b><div className="muted">consent risks</div></div></div></div>
        <Link href="/compliance/" className="card" style={{ textDecoration: 'none' }}><h3>Compliance indicators</h3>
          <div className="row" style={{ gap: 16 }}>
            <Donut parts={[{ v: inPlace + cfgOk, c: '#34d399' }, { v: gap, c: '#facc15' }, { v: cfgFail, c: '#f43f5e' }]} />
            <div style={{ fontSize: 12.5, lineHeight: 1.9 }}>
              <div><span className="dot" style={{ background: '#34d399' }} /> {inPlace + cfgOk} met</div>
              <div><span className="dot" style={{ background: '#facc15' }} /> {gap} gaps</div>
              <div><span className="dot" style={{ background: '#f43f5e' }} /> {cfgFail} failing</div></div></div>
          <div className="dim" style={{ fontSize: 11.5, marginTop: 6 }}>RBI · DPDP-aligned readiness · CERT-In · UIDAI</div></Link>
      </div>

      <div className="grid g-7-5" style={{ marginTop: 16 }}>
        <div className="card"><h3>Activity over time, latest incident <span className="r"><span className="dot" style={{ background: '#60a5fa' }} /> all events &nbsp; <span className="dot" style={{ background: '#f43f5e' }} /> suspicious</span></h3>
          <AreaChart times={times} bad={badTimes} />
          <div className="row wrap" style={{ gap: 8, marginTop: 12 }}>{['Data access', 'Cloud activity', 'Cloud configuration', 'Threat detection', 'Consent records', 'Partner activity'].map((x) => <span key={x} className="pill cat">✓ {x}</span>)}</div></div>
        <div className="card"><h3>Incidents by type</h3>
          {byScenario.size ? <HBars items={[...byScenario].map(([k, v]) => ({ k, v, c: 'linear-gradient(90deg,#fb923c,#f43f5e)' }))} /> : <div className="empty" style={{ padding: 20 }}>No incidents yet</div>}
          <h3 style={{ marginTop: 18 }}>Cloud security checks</h3>
          {p.config_results.map((c) => (
            <div key={c.control_id} className="row" style={{ padding: '5px 0', fontSize: 12.5 }}>
              <span className="dot" style={{ background: c.status === 'COMPLIANT' ? '#34d399' : c.status === 'NON_COMPLIANT' ? '#f43f5e' : '#64718e' }} />
              <span style={{ flex: 1 }}>{checkName(c.control_id)}</span><span className="muted">{c.status === 'COMPLIANT' ? 'Passing' : c.status === 'NON_COMPLIANT' ? 'Failing' : 'Unknown'}</span></div>
          ))}</div>
      </div>

      <div className="grid g-7-5" style={{ marginTop: 16 }}>
        <div className="card"><h3>Open incidents <span className="r">{alerts.length} shown</span></h3>
          {alerts.length ? (
            <table><thead><tr><th>Severity</th><th>Incident</th><th>Identity</th><th>Risk</th><th>Status</th></tr></thead><tbody>
              {alerts.map((a) => (
                <tr key={a.alert_id} className="click" onClick={() => router.push(`/incidents/?id=${a.alert_id}`)}>
                  <td><Pill sev={a.severity} /></td>
                  <td><div style={{ fontWeight: 600 }}>{a.ai?.headline ?? incidentType(a.scenario_id)}</div><div className="mono dim">{a.alert_id}</div></td>
                  <td><div className="who"><Av name={userLabel(a.user_id)} /><div>{userLabel(a.user_id)}</div></div></td>
                  <td style={{ width: 120 }}><div className="row"><b>{a.score}</b><div style={{ flex: 1 }}><SevBar pct={a.score} color={sevColor(a.severity)} /></div></div></td>
                  <td className="muted">{label(a.status)}</td></tr>
              ))}</tbody></table>
          ) : <div className="empty"><div className="big">🛡️</div>All clear. Activity from FinLend systems is being monitored.</div>}
          <h3 style={{ marginTop: 18 }}>Riskiest identities</h3>
          {risky.length ? risky.map((a) => (
            <div key={a.user_id} className="row" style={{ padding: '7px 0' }}><Av name={userLabel(a.user_id)} />
              <div style={{ width: 190 }}><div>{userLabel(a.user_id)}</div><div className="dim" style={{ fontSize: 12 }}></div></div>
              <div style={{ flex: 1 }}><SevBar pct={a.score} color={sevColor(a.severity)} /></div><b style={{ width: 30, textAlign: 'right' }}>{a.score}</b></div>
          )) : <div className="muted">No risky activity yet.</div>}
          {p.deadlines_due_soon.length > 0 && <>
            <h3 style={{ marginTop: 18 }}>Regulator deadlines due soon</h3>
            {p.deadlines_due_soon.map((d) => (
              <div key={d.alert_id + d.body} className="row" style={{ padding: '6px 0', fontSize: 12.5 }}>
                <span className="pill cat">{d.body}</span><span className="mono dim">{d.alert_id}</span><span className="sp" />
                <b className="mono">{countdown(d.due_at, DEADLINE_HOURS[d.body] ?? 6, now).txt}</b><span className="dim">{DEADLINE_LABEL[d.body]}</span></div>
            ))}</>}</div>
        <div className="card"><h3>Live activity <span className="r">{fmt(events.length)} events</span></h3>
          <div className="feed">
            {events.length ? events.slice(0, 40).map((f) => {
              const bad = BAD_ACTIONS.includes(f.action); const ic = ICON[f.action] ?? ['•', '#8e9ab5'];
              return (
                <div key={f.event_id} className={`fi ${bad ? 'bad' : ''}`}><span className="t">{hms(f.ts)}</span>
                  <span className="ic" style={{ background: ic[1] + '22', color: ic[1] }}>{ic[0]}</span>
                  <span><b>{userLabel(f.user_id)}</b> <span className="act">{label(f.action)}</span>{f.object_id ? ` ${f.object_id}` : ''}{f.destination ? ` → ${f.destination}` : ''}{f.source !== 'simulator' && <> <span className="pill cat">{f.source}</span></>}</span></div>
              );
            }) : <div className="empty">Waiting for events…</div>}</div></div>
      </div>
    </>
  );
}
