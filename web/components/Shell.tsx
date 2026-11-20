'use client';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { createContext, useCallback, useContext, useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { api, useMocks, type Alert, type CognitoGroup } from '@/lib/api';
import { incidentType, userLabel } from '@/lib/format';
import { MOCK_ROLES, useAuth } from '@/lib/auth';
import { useLoad } from '@/lib/hooks';

import { avColor, initials } from '@/lib/format';

export interface PageDef { href: string; title: string; sub: string; icon: string; groups: CognitoGroup[] }
const ALL: CognitoGroup[] = ['Analyst', 'SecurityHead', 'ComplianceHead', 'Auditor', 'Admin'];
export const PAGES: PageDef[] = [
  { href: '/', title: 'Overview', sub: 'Security posture, live activity and open incidents', icon: 'M3 13h8V3H3v10zm0 8h8v-6H3v6zm10 0h8V11h-8v10zm0-18v6h8V3h-8z', groups: ['Analyst', 'SecurityHead', 'ComplianceHead', 'Admin'] },
  { href: '/incidents/', title: 'Incidents', sub: 'Investigate, contain and approve', icon: 'M12 2 1 21h22L12 2zm1 15h-2v-2h2v2zm0-4h-2V9h2v4z', groups: ['Analyst', 'SecurityHead', 'ComplianceHead', 'Admin'] },
  { href: '/approvals/', title: 'Approvals', sub: 'Actions waiting for the Security Head', icon: 'M9 16.2 4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z', groups: ['SecurityHead', 'ComplianceHead', 'Admin'] },
  { href: '/deadlines/', title: 'Regulator deadlines', sub: 'RBI · CERT-In · Data Protection Board', icon: 'M6 2h9l5 5v15H6V2zm8 1.5V8h4.5', groups: ['Analyst', 'SecurityHead', 'ComplianceHead', 'Admin'] },
  { href: '/compliance/', title: 'Compliance', sub: 'RBI, DPDP-aligned readiness, CERT-In, UIDAI', icon: 'M12 1 3 5v6c0 5.5 3.8 10.7 9 12 5.2-1.3 9-6.5 9-12V5l-9-4z', groups: ['Analyst', 'SecurityHead', 'ComplianceHead', 'Admin'] },
  { href: '/accuracy/', title: 'Detection accuracy', sub: 'Measured on replayed scenarios and normal days', icon: 'M3 17h4v4H3zm7-6h4v10h-4zm7-8h4v18h-4z', groups: ['Admin'] },
  { href: '/audit/', title: 'Audit evidence', sub: 'Read-only access to sealed evidence', icon: 'M4 4h16v16H4zM8 8h8M8 12h8M8 16h5', groups: ['Auditor', 'SecurityHead', 'ComplianceHead', 'Admin'] },
];
export const pageFor = (path: string) => PAGES.find((p) => p.href === path || p.href === path.replace(/\/?$/, '/')) ?? PAGES[0];

// ---- shared alert list (polled once, used by every page + nav badges + toasts)
interface AlertsCtx { alerts: Alert[] | null; error: string | null; reload: () => void }
const AlertsContext = createContext<AlertsCtx>({ alerts: null, error: null, reload: () => {} });
export const useAlerts = () => useContext(AlertsContext);

// ---- toasts
interface Toast { id: number; title: string; body: string; href?: string }
const ToastContext = createContext<(t: Omit<Toast, 'id'>) => void>(() => {});
export const useToast = () => useContext(ToastContext);

function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState(''), [pw, setPw] = useState(''), [err, setErr] = useState(''), [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(''); setBusy(true);
    try { await login(email, pw); } catch (x) { setErr(x instanceof Error ? x.message : String(x)); }
    setBusy(false);
  };
  const mark = (
    <div className="mark"><svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M12 2l8 3v6c0 5-3.4 9.4-8 11-4.6-1.6-8-6-8-11V5l8-3z" fill="#fff" /><path d="M8.5 12l2.4 2.4 4.6-4.8" stroke="#f43f5e" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg></div>
  );
  return (
    <div className="login" style={{ display: 'grid' }}>
      <div className="art">
        <div className="logo">{mark}<div><b>FinShield AI</b><small>for FinLend NBFC</small></div></div>
        <div>
          <h2>Know who touched your customers&apos; KYC data. In minutes, not days.</h2>
          <p>Unified security, privacy and compliance monitoring for digital lenders. Detects insider data leaks, cloud misconfigurations, consent breaches and personal data in code, explains them in plain language, contains them automatically and keeps sealed evidence for the regulator.</p>
          <div className="feat">
            <div><b>Monitor</b>Data access, cloud activity, consent</div>
            <div><b>Investigate</b>AI root cause, mapped to RBI and DPDP-aligned controls</div>
            <div><b>Respond</b>Automatic containment with Security Head approval</div>
            <div><b>Prove</b>Hash-chained evidence, 6 h / 72 h regulator timers</div>
          </div>
        </div>
        <div className="dim" style={{ fontSize: 12 }}>AI FORGE 2026 · Team Global Nodes · Demo environment with synthetic data only</div>
      </div>
      <div className="form">
        <form onSubmit={submit}>
          <h2 style={{ margin: '0 0 4px' }}>Sign in</h2>
          <div className="muted" style={{ marginBottom: 22 }}>FinShield Security Operations Console</div>
          <label>Work email</label>
          <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@finlend.demo" autoComplete="username" required />
          <label>Password</label>
          <input type="password" value={pw} onChange={(e) => setPw(e.target.value)} placeholder="••••••••" autoComplete="current-password" required />
          <div className="err">{err}</div>
          <button className="btn primary" style={{ width: '100%', justifyContent: 'center', padding: 12 }} disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
          <div className="dim" style={{ fontSize: 11.5, marginTop: 22 }}>Access is based on your role.</div>
        </form>
      </div>
    </div>
  );
}

function Frame({ children }: { children: ReactNode }) {
  const { session, logout, mockRole, setMockRole } = useAuth();
  const mocks = useMocks();
  const path = usePathname();
  const router = useRouter();
  const groups = session!.groups;
  const allowed = PAGES.filter((p) => p.groups.some((g) => groups.includes(g)));
  const cur = pageFor(path);
  const canSee = allowed.some((p) => p.href === cur.href);

  useEffect(() => { if (!canSee && allowed[0]) router.replace(allowed[0].href); }, [canSee, allowed, router]);

  const { data: alerts, error, reload } = useLoad(() => api.listAlerts(), [], 2500);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);
  const push = useCallback((t: Omit<Toast, 'id'>) => {
    const id = nextId.current++;
    setToasts((x) => [...x, { ...t, id }]);
    setTimeout(() => setToasts((x) => x.filter((y) => y.id !== id)), 9000);
  }, []);
  const known = useRef<Set<string> | null>(null);
  useEffect(() => {
    if (!alerts) return;
    if (known.current) alerts.filter((a) => !known.current!.has(a.alert_id) && a.severity !== 'MEDIUM')
      .forEach((a) => push({ title: `${a.severity}: ${incidentType(a.scenario_id)}`, body: `${userLabel(a.user_id)} · risk ${a.score}`, href: `/incidents/?id=${a.alert_id}` }));
    known.current = new Set(alerts.map((a) => a.alert_id));
  }, [alerts, push]);

  const open = (alerts ?? []).filter((a) => !['CLOSED', 'RELEASED'].includes(a.status)).length;
  const pend = (alerts ?? []).filter((a) => a.status === 'AWAITING_APPROVAL').length;
  const badge = (href: string) => (href === '/incidents/' ? open : href === '/approvals/' ? pend : 0);
  const name = session!.name;

  return (
    <ToastContext.Provider value={push}>
      <AlertsContext.Provider value={{ alerts, error, reload }}>
        <div className="app">
          <aside>
            <div className="logo">
              <div className="mark"><svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M12 2l8 3v6c0 5-3.4 9.4-8 11-4.6-1.6-8-6-8-11V5l8-3z" fill="#fff" /><path d="M8.5 12l2.4 2.4 4.6-4.8" stroke="#f43f5e" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" /></svg></div>
              <div><b>FinShield AI</b><small>Security Operations</small></div>
            </div>
            <nav className="nav">
              {allowed.map((p) => (
                <Link key={p.href} href={p.href} className={`navlink ${p.href === cur.href ? 'on' : ''}`}>
                  <svg width="17" height="17" viewBox="0 0 24 24" fill="currentColor"><path d={p.icon} /></svg>{p.title}
                  {badge(p.href) > 0 && <span className="badge">{badge(p.href)}</span>}
                </Link>
              ))}
            </nav>
            <div className="side-foot">
              {mocks && (
                <div><label>View as (demo)</label>
                  <select value={mockRole} onChange={(e) => setMockRole(e.target.value as CognitoGroup)}>{MOCK_ROLES.map((r) => <option key={r}>{r}</option>)}</select></div>
              )}
              <div className="ucard">
                <div className="av" style={{ background: avColor(name) }}>{initials(name)}</div>
                <div style={{ minWidth: 0 }}><div style={{ fontWeight: 700, fontSize: 13 }}>{name}</div><div className="dim" style={{ fontSize: 11.5 }}>{groups.join(', ') || 'no group'}</div></div>
              </div>
              {!mocks && <button className="btn ghost" onClick={logout} style={{ justifyContent: 'center' }}>⎋ Sign out</button>}
              <div className="dim" style={{ fontSize: 11.5 }}>FinLend NBFC<br />{mocks ? '● Demo data' : error ? '● Offline' : '● Live'}</div>
            </div>
          </aside>
          <div className="main">
            <div className="top">
              <div><h1>{cur.title}</h1><div className="sub">{cur.sub}</div></div>
              <span className="sp" />
              <div className="live"><span className="pulse" /> Live monitoring</div>
              <div className="live" title="Activity from FinLend systems and the cloud account">⇄ Sources connected</div>
            </div>
            <div className="content">{canSee ? children : null}</div>
          </div>
        </div>
        <div className="toasts">
          {toasts.map((t) => (
            <div key={t.id} className="toast" onClick={() => { setToasts((x) => x.filter((y) => y.id !== t.id)); if (t.href) router.push(t.href); }}>
              <div className="row" style={{ gap: 8, marginBottom: 4 }}><span className="pill Critical">New incident</span><b>{t.title}</b></div>
              <div className="muted" style={{ fontSize: 12.5 }}>{t.body}</div>
            </div>
          ))}
        </div>
      </AlertsContext.Provider>
    </ToastContext.Provider>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const { session, ready } = useAuth();
  if (!ready) return null;
  if (!session) return <Login />;
  return <Frame>{children}</Frame>;
}
