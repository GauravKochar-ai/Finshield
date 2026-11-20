import type { Severity } from './api';

export const fmt = (n: number | string | null | undefined): string =>
  n == null || n === '' ? '–' : Number(n).toLocaleString('en-IN');
/** "2026-11-20T23:49:02+05:30" -> "2026-11-20 23:49:02" (the API already sends IST). */
export const ts = (s?: string | null): string => (s ? s.replace('T', ' ').slice(0, 19) : '');
export const hm = (s?: string | null): string => (s ? s.slice(11, 16) : '');
export const hms = (s?: string | null): string => (s ? s.slice(11, 19) : '');
export const bytes = (b?: number | null): string =>
  !b ? '0 B' : b >= 1e9 ? (b / 1e9).toFixed(1) + ' GB' : b >= 1e6 ? (b / 1e6).toFixed(0) + ' MB' : fmt(b) + ' B';
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
