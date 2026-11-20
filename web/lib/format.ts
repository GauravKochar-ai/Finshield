import type { Severity } from './api';

export const fmt = (n: number | string | null | undefined): string =>
  n == null || n === '' ? '–' : Number(n).toLocaleString('en-IN');
/** "2026-11-20T23:49:02+05:30" -> "2026-11-20 23:49:02" (the API already sends IST). */
export const ts = (s?: string | null): string => (s ? s.replace('T', ' ').slice(0, 19) : '');
export const hm = (s?: string | null): string => (s ? s.slice(11, 16) : '');
export const hms = (s?: string | null): string => (s ? s.slice(11, 19) : '');
export const bytes = (b?: number | null): string =>
  !b ? '0 B' : b >= 1e9 ? (b / 1e9).toFixed(1) + ' GB' : b >= 1e6 ? (b / 1e6).toFixed(0) + ' MB' : fmt(b) + ' B';
/** AWS role or user name without the stack prefix and the CloudFormation suffix:
 *  "finshield-dev-KycLabelFunctionRole-idBAuQb6V1gg" -> "KycLabelFunctionRole". */
export const shortName = (n?: string | null): string =>
  (n || '').replace(/^finshield-[a-z0-9]+-/i, '').replace(/-[A-Za-z0-9]{10,14}$/, '');
/** User id for display. Unknown AWS identities arrive as "unmapped:<arn>"; show "aws:<role or user name>",
 *  never the full ARN. Known users (u-017, svc-ckyc) are shown as they are. */
export const userLabel = (id?: string | null): string => {
  if (!id) return '-';
  if (!id.startsWith('unmapped:')) return id;
  const arn = id.slice('unmapped:'.length);
  const m = arn.match(/assumed-role\/([^/]+)/) || arn.match(/:(?:role|user)\/([^/]+)/);
  return `aws:${shortName(m ? m[1] : arn.split(/[/:]/).pop()) || 'unknown'}`;
};
export const initials = (n?: string): string =>
  (n || '?').split(/[\s.\-_]+/).filter(Boolean).map((x) => x[0]).slice(0, 2).join('').toUpperCase();
export const avColor = (s: string): string =>
  ['#60a5fa', '#2dd4bf', '#a78bfa', '#fb923c', '#f472b6', '#facc15', '#34d399'][
    [...String(s)].reduce((a, c) => a + c.charCodeAt(0), 0) % 7
  ];
/** CRITICAL -> Critical (CSS class names). */
export const sevCls = (s: string): string => s.charAt(0) + s.slice(1).toLowerCase();
export const SEV_COLOR: Record<string, string> = {
  CRITICAL: '#f43f5e', HIGH: '#fb923c', MEDIUM: '#facc15', LOGGED: '#94a3b8',
};
export const SEVERITIES: Severity[] = ['CRITICAL', 'HIGH', 'MEDIUM'];
export const label = (s: string): string => s.replace(/_/g, ' ').toLowerCase();

export const DEADLINE_HOURS: Record<string, number> = { RBI: 6, 'CERT-In': 6, DPB: 72 };
export const DEADLINE_LABEL: Record<string, string> = {
  RBI: 'RBI incident report', 'CERT-In': 'CERT-In report', DPB: 'Data Protection Board notice',
};
export const REPORT_LABEL: Record<string, string> = {
  RBI_INCIDENT: 'RBI incident report', CERTIN_FORM: 'CERT-In form', DPB_NOTICE: 'DPB notice', CUSTOMER_NOTICE: 'Customer notice',
};

export function countdown(due: string, hours: number, now = Date.now()): { txt: string; p: number } {
  const ms = new Date(due).getTime() - now;
  if (ms <= 0) return { txt: 'Overdue', p: 1 };
  const h = Math.floor(ms / 36e5), m = Math.floor((ms % 36e5) / 6e4), s = Math.floor((ms % 6e4) / 1e3);
  return { txt: `${h}h ${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}s`, p: Math.min(1, 1 - ms / (hours * 36e5)) };
}

/** One-line, human description of a signal's facts. Falls back to key: value pairs for unknown shapes. */
export function signalText(code: string, f: Record<string, unknown>): string {
  const g = (k: string) => f[k] as never;
  switch (code) {
    case 'S1': return `${fmt(g('downloads_15m'))} downloads in 15 min vs usual ${fmt(g('baseline_p95'))}, ${fmt(g('ratio'))}× normal`;
    case 'S3': return `Assumed ${g('role') ?? 'a privileged role'}${f.covering_approval === false ? ' with no covering approval' : ''}`;
    case 'S4': return `${bytes(g('bytes'))} sent to ${g('destination')} (not on allowlist)${f.minutes_after_downloads != null ? `, ${g('minutes_after_downloads')} min after downloads` : ''}`;
    case 'S5': return [
      f.new_device ? `new device ${g('new_device')}` : '',
      Array.isArray(f.cities) && f.cities.length > 1 ? `${(f.cities as string[]).join(' → ')} (${fmt(g('distance_km'))} km in ${g('window_minutes')} min)` : '',
      f.mfa_pushes ? `${g('mfa_pushes')} MFA pushes` : '',
    ].filter(Boolean).join(' · ') || genericFacts(f);
    case 'S6': return `Active at ${g('local_time')}; usual hours ${g('usual_hours')}`;
    default: return genericFacts(f);
  }
}
const genericFacts = (f: Record<string, unknown>): string =>
  Object.entries(f).map(([k, v]) => `${label(k)}: ${typeof v === 'object' ? JSON.stringify(v) : String(v)}`).join(' · ');

/** Client-facing names. Internal ids (SC-01, rule ids, Lambda action codes) are never shown. */
export const INCIDENT_TYPE: Record<string, string> = {
  'SC-01': 'Insider data export', 'SC-01b': 'Insider data export', 'SC-02': 'Approved batch upload', 'SC-03': 'Approved audit export',
  'SC-04': 'Unassigned customer access', 'SC-05': 'Minor off-hours activity', 'SC-06': 'Compromised admin account',
  'SC-07': 'Consent breach', 'SC-08': 'Suspicious disbursement', 'SC-09': 'Public KYC storage', 'SC-10': 'Approval limit exceeded',
};
export const incidentType = (scenario?: string | null): string => (scenario && INCIDENT_TYPE[scenario]) || 'Security incident';
export const CHECK_NAME: Record<string, string> = {
  's3-bucket-public-read-prohibited': 'KYC document storage is not publicly readable',
  'cloudtrail-enabled': 'Audit logging is switched on',
  'mfa-enabled-for-iam-console-access': 'Multi-factor sign-in enforced for admin users',
};
export const checkName = (id: string): string => CHECK_NAME[id] ?? label(id.replace(/-/g, ' '));
export const ACTION_NAME: Record<string, string> = {
  REVOKE_SESSIONS: 'Active sessions signed out', DEACTIVATE_KEYS: 'Access keys disabled', BUCKET_DENY: 'KYC storage access blocked for the account',
  DNS_BLOCK: 'Outbound upload destination blocked', LOCK_PRINCIPAL: 'Account locked',
};
export const actionName = (a: string): string => ACTION_NAME[a] ?? label(a);

// ---------------------------------------------------------------- incident type from what actually fired
const SIGNAL_TYPE: Record<string, string> = {
  S1: 'Unusual KYC download volume', S2: 'Slow data leak', S3: 'Privileged role used without approval', S4: 'Data sent to an external site',
  S5: 'Risky sign-in', S6: 'Off-hours activity', S7: 'Access to unassigned customers', S8: 'Audit logging tampered',
  S9: 'Consent breach', S10: 'Suspicious disbursement', S11: 'Misconfigured sensitive resource',
};
export function alertType(a: { signals: { code: string; points: number }[] }): string {
  const top = [...a.signals].sort((x, y) => y.points - x.points)[0];
  return (top && SIGNAL_TYPE[top.code]) || 'Security incident';
}

// ---------------------------------------------------------------- cloud checks: group per rule, hide ids and ARNs
const CHECKS: [string, string, string][] = [
  ['s3-bucket-public-read-prohibited', 'Document storage is not publicly readable', 'storage locations'],
  ['cloudtrail-enabled', 'Audit logging is switched on', 'accounts'],
  ['mfa-enabled-for-iam-console-access', 'Multi-factor sign-in enforced for admin users', 'admin users'],
];
export interface CheckGroup { name: string; unit: string; total: number; pass: number; fail: string[]; unknown: number }
export function groupChecks(rows: { control_id: string; status: string }[]): CheckGroup[] {
  const m = new Map<string, CheckGroup>();
  rows.forEach((r) => {
    const parts = r.control_id.split(':');
    const hit = CHECKS.find((c) => r.control_id.includes(c[0]));
    const key = hit ? hit[0] : parts[1] ?? r.control_id;
    const g = m.get(key) ?? { name: hit ? hit[1] : label(key.replace(/^finshield-[a-z]+-/, '').replace(/-/g, ' ')), unit: hit ? hit[2] : 'resources', total: 0, pass: 0, fail: [], unknown: 0 };
    g.total += 1;
    if (r.status === 'COMPLIANT') g.pass += 1;
    else if (r.status === 'NON_COMPLIANT') g.fail.push((parts[parts.length - 1] || '').replace(/-\d{12}$/, ''));
    else g.unknown += 1;
    m.set(key, g);
  });
  return [...m.values()];
}

// ---------------------------------------------------------------- readable event runs
export function cleanRole(r?: string | null): string {
  if (!r) return '';
  const n = r.split('/').pop()!.replace(/^finshield-[a-z]+-/i, '').replace(/-[A-Za-z0-9]{10,14}$/, '').replace(/Role$/, '');
  return n.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/[-_]/g, ' ').trim();
}
export interface EventRun { first: string; last: string; n: number; action: string; user_id: string; bytes: number; sample: Record<string, any> }
export function collapseEvents(evs: { ts: string; action: string; user_id: string; bytes?: number | null }[]): EventRun[] {
  const out: EventRun[] = [];
  [...evs].sort((a, b) => a.ts.localeCompare(b.ts)).forEach((e) => {
    const l = out[out.length - 1];
    if (l && l.action === e.action && l.user_id === e.user_id) { l.n += 1; l.last = e.ts; l.bytes += e.bytes ?? 0; }
    else out.push({ first: e.ts, last: e.ts, n: 1, action: e.action, user_id: e.user_id, bytes: e.bytes ?? 0, sample: e });
  });
  return out;
}
export function runText(r: EventRun): string {
  const s = r.sample, n = r.n, plural = n > 1;
  switch (r.action) {
    case 'DOWNLOAD': case 'PRESIGN': return `${fmt(n)} KYC document${plural ? 's' : ''} downloaded${r.bytes ? ` (${bytes(r.bytes)})` : ''}${!plural && s.object_id ? ` · ${s.object_id}` : ''}`;
    case 'KYC_FILE_UPLOADED': return `${fmt(n)} KYC file${plural ? 's' : ''} uploaded to storage${!plural && s.object_id ? ` · ${s.object_id}` : ''}`;
    case 'MFA_PUSH': return `${fmt(n)} sign-in approval request${plural ? 's' : ''} (MFA)`;
    case 'ASSUME_ROLE': return `Switched to the ${cleanRole(s.role)} role`;
    case 'UPLOAD_EXTERNAL': return `Upload${r.bytes ? ` of ${bytes(r.bytes)}` : ''} to ${s.destination ?? 'an outside site'}`;
    case 'LOGIN': return `Signed in${s.city ? ` from ${s.city}` : ''}${s.device_id ? ` on device ${s.device_id}` : ''}`;
    case 'LOGGING_CHANGE': return 'Audit logging was changed';
    case 'CONFIG_NONCOMPLIANT': return 'A cloud security check failed';
    case 'GUARDDUTY_FINDING': return 'Threat detection finding';
    case 'DISBURSE': return `Loan disbursed${s.amount_inr ? ` (₹${fmt(s.amount_inr)})` : ''}`;
    case 'BANK_ACCOUNT_CHANGE': return 'Borrower bank account changed';
    default: return `${label(r.action)}${plural ? ` ×${fmt(n)}` : ''}`;
  }
}

const EVIDENCE_STEP: Record<string, string> = {
  ALERT_RAISED: 'Incident detected', DEADLINES_SET: 'Regulator timers started', AI_EXPLAINED: 'AI investigation', REPORTS_DRAFTED: 'Reports drafted',
  CONTAIN_REVOKE_SESSIONS: 'Sessions signed out', CONTAIN_DEACTIVATE_KEYS: 'Access keys disabled', CONTAIN_BUCKET_DENY: 'KYC storage blocked',
  CONTAIN_DNS_BLOCK: 'Upload site blocked', DECISION_APPROVED: 'Lock-down approved', DECISION_REJECTED: 'Lock-down rejected', QUARANTINE: 'Account locked',
  RELEASED: 'Access restored', ESCALATED: 'Escalated to Compliance Head', CLOSED: 'Incident closed', EVIDENCE_EXPORTED: 'Evidence archived',
};
export const evidenceStep = (t: string): string => EVIDENCE_STEP[t] ?? label(t).replace(/^./, (c) => c.toUpperCase());
