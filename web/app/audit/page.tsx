'use client';
import { useState } from 'react';
import { can } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useAlerts } from '@/components/Shell';
import { AlertTable } from '@/components/AlertTable';
import { EvidenceChain } from '@/components/EvidenceChain';
import { Empty, ErrorCard, Loading } from '@/components/ui';

export default function Audit() {
  const { session } = useAuth();
  const { alerts, error } = useAlerts();
  const [sel, setSel] = useState<string | null>(null);
  if (error && !alerts) return <ErrorCard message={error} />;
  if (!alerts) return <Loading />;
  if (!alerts.length) return <Empty icon="📁">No cases yet.</Empty>;
  const id = alerts.find((a) => a.alert_id === sel)?.alert_id ?? alerts[0].alert_id;
  return (
    <>
      <div className="readonly">🔒 Read-only view. Evidence can be viewed, verified and exported, never changed.</div>
      <AlertTable alerts={alerts} selected={id} onSelect={setSel} full />
      <div style={{ marginTop: 16 }}><EvidenceChain key={id} alertId={id} canTamper={can.admin(session!.groups)} compact /></div>
    </>
  );
}
