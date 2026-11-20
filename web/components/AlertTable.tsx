'use client';
import type { Alert } from '@/lib/api';
import { alertType, hm, label, ts } from '@/lib/format';
import { useWho } from '@/lib/people';
import { Pill } from './ui';
import { WhoCell } from './WhoCell';

export function AlertTable({ alerts, selected, onSelect, full }: { alerts: Alert[]; selected: string | null; onSelect: (id: string) => void; full?: boolean }) {
  const who = useWho(alerts.map((a) => a.user_id));
  return (
    <div className="card" style={{ padding: '10px 14px' }}>
      <table className="fixed"><colgroup><col style={{ width: 100 }} /><col /><col style={{ width: '26%' }} /><col style={{ width: 60 }} /><col style={{ width: 90 }} /><col style={{ width: full ? 160 : 80 }} /><col style={{ width: 140 }} /></colgroup>
        <thead><tr><th>Severity</th><th>Incident</th><th>Identity</th><th>Risk</th><th>Customers</th><th>Detected</th><th>Status</th></tr></thead><tbody>
        {alerts.map((a) => (
          <tr key={a.alert_id} className={`click ${a.alert_id === selected ? 'sel' : ''}`} onClick={() => onSelect(a.alert_id)}>
            <td><Pill sev={a.severity} /></td>
            <td><b>{alertType(a)}</b><div className="mono dim">{a.alert_id}</div></td>
            <td><WhoCell who={who(a.user_id)} /></td>
            <td><b>{a.score}</b></td><td>{a.customers_affected}</td>
            <td className="mono">{full ? ts(a.detected_at) : hm(a.detected_at)}</td><td className="muted" style={{ textTransform: 'capitalize' }}>{label(a.status)}</td>
          </tr>
        ))}</tbody></table>
    </div>
  );
}
