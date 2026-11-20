'use client';
import { useState } from 'react';
import { api, type EvidenceEntry, type VerifyResult } from '@/lib/api';
import { useLoad } from '@/lib/hooks';
import { evidenceStep, hm } from '@/lib/format';

/** Hash-chain view with verify, tamper demo (Admin) and JSON export. Entries are read-only. */
export function EvidenceChain({ alertId, canTamper, compact }: { alertId: string; canTamper: boolean; compact?: boolean }) {
  const ev = useLoad<EvidenceEntry[]>(() => api.getEvidence(alertId), [alertId], 5000);
  const [verify, setVerify] = useState<{ res: VerifyResult; tampered: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const entries = ev.data ?? [];

  const run = async (tamper: boolean) => {
    setBusy(true);
    try { setVerify({ res: await (tamper ? api.tamperDemo(alertId) : api.verifyEvidence(alertId)), tampered: tamper }); }
    catch (e) { setVerify(null); alert(e instanceof Error ? e.message : String(e)); }
    setBusy(false);
  };
  const exportJson = () => {
    const a = document.createElement('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify({ alert_id: alertId, entries }, null, 1)], { type: 'application/json' }));
    a.download = `${alertId}-evidence.json`; a.click();
  };
  const v = verify?.res;
  const broken = v && !v.valid ? v.broken_at_seq : null;

  return (
    <div className="card" style={{ marginTop: compact ? 0 : 16 }}>
      <h3>Tamper-proof evidence trail <span className="r">{entries.length} sealed entries</span></h3>
      <div className="row wrap" style={{ marginBottom: 12 }}>
        {v ? <span className={`seal ${v.valid ? 'ok' : 'bad'}`}>{v.valid ? `🔒 Seal intact, all ${entries.length} entries verify` : `⚠ Seal broken at entry ${v.broken_at_seq}`}</span>
          : <span className="seal ok" style={{ opacity: .7 }}>Not verified yet</span>}
        <button className="btn" disabled={busy} onClick={() => run(false)}>Verify seal</button>
        {canTamper && <button className="btn danger" disabled={busy} onClick={() => run(true)}>Tamper test</button>}
        <button className="btn" onClick={exportJson}>⇩ Export JSON</button>
        <button className="btn ghost" onClick={() => window.print()}>Print / PDF</button>
      </div>
      {verify?.tampered && <div className="seal bad" style={{ marginBottom: 12 }}>Tamper test: one entry was changed in a copy and the seal breaks from entry {v?.broken_at_seq}. The real trail is untouched.</div>}
      {compact ? (
        <table><thead><tr><th>#</th><th>Time</th><th>Step</th><th>By</th><th>Seal</th></tr></thead><tbody>
          {entries.map((e) => <tr key={e.seq}><td>{e.seq}</td><td className="mono">{e.ts.slice(0, 19).replace('T', ' ')}</td><td>{evidenceStep(e.type)}</td><td>{e.actor.includes('@') ? e.actor : 'FinShield (automatic)'}</td><td className="mono dim">{e.hash.slice(0, 20)}…</td></tr>)}</tbody></table>
      ) : (
        <div className="chain">
          {entries.map((e, i) => (
            <div key={e.seq} style={{ display: 'contents' }}>
              {i > 0 && <div style={{ alignSelf: 'center', color: '#2c3c61' }}>→</div>}
              <div className={`blk ${broken && e.seq >= broken ? 'bad' : ''}`}><b>{e.seq}. {evidenceStep(e.type)}</b><div className="dim">{hm(e.ts)}</div><div className="h">{e.hash.slice(0, 10)}…</div></div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
