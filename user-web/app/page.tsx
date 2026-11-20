'use client';
import { useState, type FormEvent } from 'react';
import Link from 'next/link';
import { api } from '@/lib/api';
import { useLoad } from '@/lib/hooks';
import { containedText, containmentOf, useStaff } from '@/components/Gate';
import { Empty, ErrorCard, Loading } from '@/components/ui';
import { PurposeSelect } from '@/components/PurposeSelect';

export default function Customers() {
  const { me, purpose } = useStaff();
  const [input, setInput] = useState(''), [q, setQ] = useState('');
  const [bad, setBad] = useState('');
  const { data, error, err } = useLoad(() => api.customers(q || undefined, purpose), [q, purpose]);
  const contained = containmentOf(err, me);

  const search = (e: FormEvent) => {
    e.preventDefault();
    const v = input.trim().toUpperCase();
    if (v && !/^C-\d{5}$/.test(v)) { setBad('Customer ID looks like C-10001'); return; }
    setBad(''); setQ(v);
  };

  return (
    <div>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="row wrap" style={{ gap: 16 }}>
          <PurposeSelect />
          <form onSubmit={search} className="row" style={{ flex: 1, minWidth: 320 }}>
            <input className="field" placeholder="Customer ID, e.g. C-10001" value={input} onChange={(e) => setInput(e.target.value)} />
            <button className="btn primary">Search</button>
            {q && <button type="button" className="btn ghost" onClick={() => { setQ(''); setInput(''); }}>Clear</button>}
          </form>
        </div>
        {bad && <div className="err" style={{ marginTop: 8 }}>{bad}</div>}
        <div className="dim" style={{ fontSize: 12, marginTop: 8 }}>Every customer view, KYC view, download and upload is recorded with the purpose you choose.</div>
      </div>

      {contained ? <Empty icon="⛔">{containedText(contained)}</Empty>
        : error && !data ? <ErrorCard message={error} />
        : !data ? <Loading />
        : (
          <div className="card">
            <h3>{q ? `Search: ${q}` : 'My customers'} <span className="r">{data.length} shown · SAMPLE data</span></h3>
            {error && <div className="err">{error}</div>}
            {data.length === 0 ? <div className="empty">No customers found.</div> : (
              <table>
                <thead><tr><th>Customer</th><th>City</th><th>Loan</th><th>Aadhaar</th><th>PAN</th><th>Assigned to</th><th /></tr></thead>
                <tbody>
                  {data.map((c) => (
                    <tr key={c.customer_id}>
                      <td><Link href={`/customer/?id=${encodeURIComponent(c.customer_id)}`} className="mono" style={{ color: '#60a5fa' }}>{c.customer_id}</Link>{c.sample && <span className="pill Logged" style={{ marginLeft: 8 }}>SAMPLE</span>}</td>
                      <td>{c.city}</td>
                      <td className="mono">{c.loan_id}</td>
                      <td className="mono">{c.aadhaar_masked}</td>
                      <td className="mono">{c.pan_fake}</td>
                      <td className="mono dim">{c.partner_id ?? c.assigned_agent ?? '–'}</td>
                      <td><Link className="btn" href={`/customer/?id=${encodeURIComponent(c.customer_id)}`}>Open →</Link></td>
                    </tr>))}
                </tbody>
              </table>)}
          </div>)}
    </div>
  );
}
