'use client';
import { api } from '@/lib/api';
import { useLoad } from '@/lib/hooks';
import { ErrorCard, Loading } from '@/components/ui';
import { checkName, label, ts } from '@/lib/format';

const COL: Record<string, string> = { IN_PLACE: '#34d399', GAP: '#f43f5e', UNKNOWN: '#facc15', NOT_APPLICABLE: '#64718e' };
const LBL: Record<string, string> = { IN_PLACE: 'In place', GAP: 'Gap', UNKNOWN: 'Unknown', NOT_APPLICABLE: 'Not applicable' };

export default function Compliance() {
  const c = useLoad(() => api.getCompliance(), [], 15000);
  const p = useLoad(() => api.getPosture(), [], 15000);
  const pr = useLoad(() => api.getPrivacy(), [], 15000);
  if (c.error && !c.data) return <ErrorCard message={c.error} />;
  if (!c.data) return <Loading />;
  const n = (k: string) => c.data!.filter((x) => x.status === k).length;
  return (
    <>
      <div className="grid g4">{Object.keys(LBL).map((k) => <div key={k} className="card"><h3><span className="dot" style={{ background: COL[k] }} /> {LBL[k]}</h3><div className="kpi">{n(k)}</div></div>)}</div>
      <div className="card" style={{ marginTop: 16 }}>
        {c.data.map((x) => (
          <div key={x.control_id} className="ctrl"><span className="s" style={{ background: COL[x.status], boxShadow: `0 0 0 4px ${COL[x.status]}22` }} />
            <div><div className="row wrap" style={{ justifyContent: 'space-between' }}><b>{x.obligation}</b><span className="pill cat">{x.control_id}</span></div>
              <div className="muted" style={{ fontSize: 12.5, marginTop: 3 }}>{x.finshield_control}</div></div></div>
        ))}
        <p className="dim" style={{ fontSize: 12, marginTop: 14 }}>DPDP is presented as DPDP-aligned readiness and controls. FinShield&apos;s consent tracking is not a registered DPDP Consent Manager.</p></div>
      <div className="grid g2" style={{ marginTop: 16 }}>
        <div className="card"><h3>Cloud security checks</h3>
          {(p.data?.config_results ?? []).map((r) => (
            <div key={r.control_id} className="ctrl"><span className="s" style={{ background: r.status === 'COMPLIANT' ? '#34d399' : r.status === 'NON_COMPLIANT' ? '#f43f5e' : '#64718e' }} />
              <div><b style={{ fontSize: 13 }}>{checkName(r.control_id)}</b><div className="muted" style={{ fontSize: 12 }}>{label(r.status)} · checked {ts(r.last_evaluated)}</div></div></div>))}</div>
        <div className="card"><h3>Privacy findings</h3>
          {pr.data && <>
            <b style={{ fontSize: 12.5 }}>Consent risks ({pr.data.consent_risks.length})</b>
            {pr.data.consent_risks.map((x) => <div key={x.customer_id + x.issue} className="muted" style={{ fontSize: 12.5, padding: '4px 0' }}><span className="mono">{x.customer_id}</span> {x.issue}</div>)}
            <b style={{ fontSize: 12.5, display: 'block', marginTop: 12 }}>Unmasked Aadhaar files ({pr.data.unmasked_aadhaar_files.length})</b>
            {pr.data.unmasked_aadhaar_files.map((x) => <div key={x.file_id} className="muted" style={{ fontSize: 12.5, padding: '4px 0' }}><span className="mono">{x.file_id}</span> {x.customer_id} · {x.doc_type}</div>)}
            <b style={{ fontSize: 12.5, display: 'block', marginTop: 12 }}>Purpose mismatches ({pr.data.purpose_mismatches.length})</b>
            {pr.data.purpose_mismatches.map((x) => <div key={x.alert_id} className="muted" style={{ fontSize: 12.5, padding: '4px 0' }}><span className="mono">{x.alert_id}</span> {x.user_id} · {x.purpose} · {x.customers} customers</div>)}</>}</div>
      </div>
    </>
  );
}
