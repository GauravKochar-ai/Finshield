'use client';
import { PURPOSES, type Purpose } from '@/lib/api';
import { useStaff } from '@/components/Gate';
import { label } from '@/lib/format';

/** Purpose of access, sent with every staff API call (default: the user's default_purpose, kept in sessionStorage). */
export function PurposeSelect() {
  const { purpose, setPurpose } = useStaff();
  return (
    <div className="row" style={{ minWidth: 260 }}>
      <span className="muted" style={{ fontSize: 12, whiteSpace: 'nowrap' }}>Purpose of access</span>
      <select value={purpose} onChange={(e) => setPurpose(e.target.value as Purpose)}>
        {PURPOSES.map((p) => <option key={p} value={p}>{label(p)}</option>)}
      </select>
    </div>
  );
}
