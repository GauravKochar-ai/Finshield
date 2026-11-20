'use client';
import type { Alert } from '@/lib/api';
import { hm, incidentType, label, ts } from '@/lib/format';
import { Pill } from './ui';

export function AlertTable({ alerts, selected, onSelect, full }: { alerts: Alert[]; selected: string | null; onSelect: (id: string) => void; full?: boolean }) {
  return (
    <div className="card" style={{ padding: '10px 14px' }}>
      <table><thead><tr><th>Severity</th><th>Incident</th><th>Identity</th><th>Risk</th><th>Customers</th><th>Detected</th><th>Status</th></tr></thead><tbody>
        {alerts.map((a) => (
          <tr key={a.alert_id} className={`click ${a.alert_id === selected ? 'sel' : ''}`} onClick={() => onSelect(a.alert_id)}>
            <td><Pill sev={a.severity} /></td>
            <td><b>{incidentType(a.scenario_id)}</b><div className="mono dim">{a.alert_id}</div></td>
            <td>{a.user_id}<div className="dim" style={{ fontSize: 12 }}></div></td>
            <td><b>{a.score}</b></td><td>{a.customers_affected}</td>
            <td className="mono">{full ? ts(a.detected_at) : hm(a.detected_at)}</td><td className="muted">{label(a.status)}</td>
          </tr>
        ))}</tbody></table>
    </div>
  );
}
