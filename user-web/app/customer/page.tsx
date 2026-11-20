'use client';
import { Suspense, useState, type FormEvent } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { api, DOC_TYPES, useMocks, type DocType, type KycFile, type Purpose, type UploadContentType } from '@/lib/api';
import { useLoad } from '@/lib/hooks';
import { containedText, containmentOf, useStaff } from '@/components/Gate';
import { PurposeSelect } from '@/components/PurposeSelect';
import { Empty, ErrorCard, Loading } from '@/components/ui';
import { label, ts } from '@/lib/format';

const errText = (e: unknown) => (e instanceof Error ? e.message : String(e));

function KycRow({ f, purpose, onError }: { f: KycFile; purpose: Purpose; onError: (e: unknown) => void }) {
  const [img, setImg] = useState<string | null>(null), [busy, setBusy] = useState<'' | 'view' | 'download'>('');
  const view = async () => {
    if (img) { setImg(null); return; }
    setBusy('view');
    try { setImg((await api.kycUrl(f.file_id, purpose, 'view')).url); } catch (e) { onError(e); }
    setBusy('');
  };
  const download = async () => {
    setBusy('download');
    try {
      const { url } = await api.kycUrl(f.file_id, purpose, 'download');
      const a = document.createElement('a');
      a.href = url; a.download = f.file_id; a.rel = 'noreferrer';
      document.body.appendChild(a); a.click(); a.remove();
    } catch (e) { onError(e); }
    setBusy('');
  };
  return (
    <>
      <tr>
        <td><b>{f.doc_type}</b><div className="mono dim">{f.file_id}</div></td>
        <td>{f.available ? `${f.size_kb} KB` : '–'}</td>
        <td>{f.ai_label ?? '–'}{f.unmasked_aadhaar_flag && <span className="pill Critical" style={{ marginLeft: 8 }}>full Aadhaar visible</span>}</td>
        <td style={{ textAlign: 'right' }}>
          {f.available ? (
            <div className="row" style={{ justifyContent: 'flex-end' }}>
              <button className="btn" disabled={!!busy} onClick={view}>{busy === 'view' ? '…' : img ? 'Hide' : '👁 View'}</button>
              <button className="btn" disabled={!!busy} onClick={download}>{busy === 'download' ? '…' : '⬇ Download'}</button>
            </div>
          ) : <span className="muted">not uploaded</span>}
        </td>
      </tr>
      {img && (
        <tr><td colSpan={4}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={img} alt={`${f.doc_type} document (SAMPLE)`} style={{ maxWidth: '100%', maxHeight: 420, borderRadius: 12, border: '1px solid var(--line)' }} />
        </td></tr>
      )}
    </>
  );
}

function Upload({ cid, purpose, onDone, onError }: { cid: string; purpose: Purpose; onDone: (msg: string) => void; onError: (e: unknown) => void }) {
  const [doc, setDoc] = useState<DocType>('PAN'), [file, setFile] = useState<File | null>(null), [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    const type = file.type as UploadContentType;
    if (type !== 'image/png' && type !== 'image/jpeg') { onError(new Error('Only PNG or JPEG images can be uploaded.')); return; }
    setBusy(true);
    try {
      const up = await api.kycUpload(cid, doc, purpose, type);
      if (!useMocks()) {
        const res = await fetch(up.url, { method: up.method, headers: up.headers, body: file });
        if (!res.ok) throw new Error(`Upload to storage failed (HTTP ${res.status})`);
      }
      onDone(`${up.file_id} uploaded${useMocks() ? ' (mock mode, nothing stored)' : ''}`);
      setFile(null);
      (e.target as HTMLFormElement).reset();
    } catch (x) { onError(x); }
    setBusy(false);
  };
  return (
    <form onSubmit={submit} className="row wrap" style={{ gap: 10 }}>
      <select value={doc} onChange={(e) => setDoc(e.target.value as DocType)} style={{ width: 150 }}>
        {DOC_TYPES.map((d) => <option key={d} value={d}>{d}</option>)}
      </select>
      <input type="file" accept="image/png,image/jpeg" onChange={(e) => setFile(e.target.files?.[0] ?? null)} style={{ flex: 1, minWidth: 200 }} />
      <button className="btn primary" disabled={!file || busy}>{busy ? 'Uploading…' : '⬆ Upload'}</button>
    </form>
  );
}

function Customer() {
  const id = (useSearchParams().get('id') ?? '').toUpperCase();
  const { me, purpose, reloadMe } = useStaff();
  const [msg, setMsg] = useState<{ text: string; bad?: boolean } | null>(null);
  const [actionErr, setActionErr] = useState<unknown>(null);
  const valid = /^C-\d{5}$/.test(id);
  const cust = useLoad(() => (valid ? api.customer(id, purpose) : Promise.resolve(null)), [id, purpose]);
  const cons = useLoad(() => (valid ? api.consent(id, purpose) : Promise.resolve(null)), [id, purpose]);

  const onError = (e: unknown) => {
    if (containmentOf(e, me)) { setActionErr(e); reloadMe(); return; }
    setMsg({ text: errText(e), bad: true });
  };
  const contained = containmentOf(actionErr, me) ?? containmentOf(cust.err, me) ?? containmentOf(cons.err, me);

  const back = <Link href="/" className="btn ghost" style={{ marginBottom: 14 }}>← My customers</Link>;
  if (!valid) return <div>{back}<Empty icon="🔎">Open a customer from the list (customer ID like C-10001).</Empty></div>;
  if (contained) return <div>{back}<Empty icon="⛔">{containedText(contained)}</Empty></div>;

  const c = cust.data, k = cons.data;
  return (
    <div>
      <div className="row wrap" style={{ marginBottom: 14 }}>{back}<span className="sp" /><PurposeSelect /></div>
      {msg && <div className={msg.bad ? 'err' : 'readonly'} style={{ marginBottom: 12 }}>{msg.text}</div>}
      {cust.error && !c ? <ErrorCard message={cust.error} /> : !c ? <Loading /> : (
        <div className="grid g-7-5">
          <div className="grid" style={{ alignContent: 'start' }}>
            <div className="card">
              <h3>Customer <span className="r">SAMPLE data</span></h3>
              <div className="row" style={{ marginBottom: 12 }}><span className="kpi mono" style={{ fontSize: 26 }}>{c.customer_id}</span>{c.sample && <span className="pill Logged">SAMPLE</span>}</div>
              <table><tbody>
                <tr><td className="muted">City</td><td>{c.city}</td></tr>
                <tr><td className="muted">Loan</td><td className="mono">{c.loan_id}</td></tr>
                <tr><td className="muted">Aadhaar</td><td className="mono">{c.aadhaar_masked}</td></tr>
                <tr><td className="muted">PAN</td><td className="mono">{c.pan_fake}</td></tr>
                <tr><td className="muted">Assigned agent</td><td className="mono">{c.assigned_agent ?? '–'}</td></tr>
                <tr><td className="muted">Partner</td><td className="mono">{c.partner_id ?? '–'}</td></tr>
              </tbody></table>
            </div>
            <div className="card">
              <h3>KYC documents <span className="r">purpose: {label(purpose)}</span></h3>
              <table>
                <thead><tr><th>Document</th><th>Size</th><th>Label</th><th /></tr></thead>
                <tbody>{c.kyc_files.map((f) => <KycRow key={f.file_id} f={f} purpose={purpose} onError={onError} />)}</tbody>
              </table>
            </div>
            <div className="card">
              <h3>Upload KYC document <span className="r">PNG or JPEG</span></h3>
              <Upload cid={c.customer_id} purpose={purpose} onError={onError} onDone={(t) => { setMsg({ text: t }); cust.reload(); }} />
            </div>
          </div>
          <div className="card" style={{ alignSelf: 'start' }}>
            <h3>Consent ledger <span className="r">read-only</span></h3>
            {cons.error && !k ? <div className="err">{cons.error}</div> : !k ? <div className="muted">Loading…</div> : (
              <>
                <div className={`seal ${k.purpose_consented ? 'ok' : 'bad'}`} style={{ marginBottom: 14 }}>
                  {k.purpose_consented ? '✓' : '✕'} {label(k.purpose)}: {k.purpose_consented ? 'consented' : 'not consented'}
                </div>
                <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>Purposes consented</div>
                <div className="row wrap" style={{ marginBottom: 14 }}>{k.purposes.length ? k.purposes.map((p) => <span key={p} className="pill real">{label(p)}</span>) : <span className="dim">none</span>}</div>
                <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>Withdrawn</div>
                <div className="row wrap" style={{ marginBottom: 14 }}>{k.withdrawn.length ? k.withdrawn.map((p) => <span key={p} className="pill Critical">{label(p)}</span>) : <span className="dim">none</span>}</div>
                <div className="dim" style={{ fontSize: 12 }}>Given {ts(k.given_at) || '–'} · notice {k.notice_version ?? '–'}{k.sample ? ' · SAMPLE' : ''}</div>
              </>)}
          </div>
        </div>)}
    </div>
  );
}

export default function CustomerPage() {
  return <Suspense fallback={<Loading />}><Customer /></Suspense>;
}
