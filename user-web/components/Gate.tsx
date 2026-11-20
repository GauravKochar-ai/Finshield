'use client';
import { createContext, useCallback, useContext, useEffect, useState, type FormEvent, type ReactNode } from 'react';
import Link from 'next/link';
import { api, ApiError, useMocks, type Purpose, type StaffContainment, type StaffMe } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useLoad } from '@/lib/hooks';
import { Av, Loading } from '@/components/ui';
import { label } from '@/lib/format';

interface StaffCtx {
  me: StaffMe;
  purpose: Purpose;
  setPurpose: (p: Purpose) => void;
  reloadMe: () => void;
}
const Ctx = createContext<StaffCtx>(null as never);
export const useStaff = () => useContext(Ctx);

const PURPOSE_KEY = 'fl_purpose';

/** "Access denied: FinShield containment is in place (alert …, mode …)" */
export const containedText = (c: Partial<StaffContainment> | null | undefined): string =>
  `Access denied: FinShield containment is in place (alert ${c?.alert_id ?? 'unknown'}, mode ${c?.mode ?? 'unknown'})`;

/** Containment details for a 403 ACCESS_CONTAINED: from the error body if present, else from /staff/me. */
export function containmentOf(e: unknown, me: StaffMe): Partial<StaffContainment> | null {
  if (!(e instanceof ApiError) || e.code !== 'ACCESS_CONTAINED') return null;
  const d = (e.detail ?? {}) as Record<string, unknown>;
  const nested = (d.containment ?? d.details ?? {}) as Record<string, unknown>;
  const pick = (k: string) => (d[k] ?? nested[k]) as string | undefined;
  return { alert_id: pick('alert_id') ?? me.containment?.alert_id, mode: (pick('mode') ?? me.containment?.mode) as StaffContainment['mode'] };
}

const Footer = () => (
  <div className="dim" style={{ textAlign: 'center', fontSize: 12, padding: '18px 26px 26px', borderTop: '1px solid var(--line)' }}>
    Activity on this portal is monitored by FinShield. All customer data shown is SAMPLE (synthetic).
  </div>
);

function StaffShell({ children }: { children: ReactNode }) {
  const { session, logout } = useAuth();
  const mocks = useMocks();
  const { data: me, error, err, reload } = useLoad(() => api.me(), [session?.email], 30_000);
  const [purpose, setPurposeState] = useState<Purpose | null>(null);

  useEffect(() => {
    if (!me || purpose) return;
    setPurposeState((sessionStorage.getItem(PURPOSE_KEY) as Purpose) || me.default_purpose);
  }, [me, purpose]);
  const setPurpose = useCallback((p: Purpose) => {
    sessionStorage.setItem(PURPOSE_KEY, p);
    setPurposeState(p);
  }, []);

  let body: ReactNode;
  if (err instanceof ApiError && err.code === 'STAFF_NOT_MAPPED') {
    body = <div className="card"><div className="empty"><div className="big">🔒</div>This account is in the Staff group but is not mapped to a FinLend staff user.</div></div>;
  } else if (err instanceof ApiError && err.httpStatus === 403 && !me) {
    body = <div className="card"><div className="empty"><div className="big">🔒</div>This account cannot use the staff API ({err.code}).</div></div>;
  } else if (!me || !purpose) {
    body = error ? <div className="card"><div className="empty"><div className="big">⚠</div>Cannot reach the FinLend Ops API<br /><span className="mono">{error}</span></div></div> : <Loading />;
  } else {
    body = <Ctx.Provider value={{ me, purpose, setPurpose, reloadMe: reload }}>{children}</Ctx.Provider>;
  }

  return (
    <div className="main" style={{ minHeight: '100vh' }}>
      <div className="top">
        <Link href="/" style={{ textDecoration: 'none' }}><h1>FinLend Ops</h1><div className="sub">Staff portal · loan servicing and KYC · SAMPLE data</div></Link>
        <span className="sp" />
        {me && (
          <div className="ucard">
            <Av name={me.name_pseudo} size={28} />
            <div style={{ fontSize: 12.5 }}><b>{me.name_pseudo}</b> <span className="mono dim">{me.user_id}</span><br /><span className="muted">{me.role} · {label(me.team)} · scope {me.access_scope}</span></div>
          </div>
        )}
        <div className="live">{mocks ? '● Mock data' : `● ${session?.email}`}</div>
        {!mocks && <button className="btn ghost" onClick={logout}>⎋ Sign out</button>}
      </div>
      {me?.containment && (
        <div className="row" style={{ background: 'rgba(244,63,94,.16)', borderBottom: '1px solid rgba(244,63,94,.55)', color: '#fecdd3', padding: '12px 26px', fontWeight: 600 }}>
          ⛔ Your access to customer data is restricted: FinShield containment is in place (alert <span className="mono">{me.containment.alert_id}</span>, status {me.containment.status}, mode {me.containment.mode}). Contact your security team.
        </div>
      )}
      <div className="content" style={{ flex: 1 }}>{body}</div>
      <Footer />
    </div>
  );
}

/** Sign-in gate. Only the Staff group may use FinLend Ops. */
export function Gate({ children }: { children: ReactNode }) {
  const { session, ready, login, logout } = useAuth();
  const [email, setEmail] = useState(''), [pw, setPw] = useState(''), [errMsg, setErrMsg] = useState(''), [busy, setBusy] = useState(false);
  if (!ready) return null;
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErrMsg(''); setBusy(true);
    try { await login(email, pw); } catch (x) { setErrMsg(x instanceof Error ? x.message : String(x)); }
    setBusy(false);
  };
  if (!session) return (
    <div className="login" style={{ display: 'grid', gridTemplateColumns: '1fr' }}>
      <div className="form"><form onSubmit={submit}>
        <h2 style={{ margin: '0 0 4px' }}>FinLend Ops — staff portal (SAMPLE data)</h2>
        <div className="muted" style={{ marginBottom: 22 }}>Sign in with your FinLend staff account</div>
        <label>Email</label><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
        <label>Password</label><input type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="current-password" required />
        <div className="err">{errMsg}</div>
        <button className="btn primary" style={{ width: '100%', justifyContent: 'center', padding: 12 }} disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <div className="dim" style={{ fontSize: 12, marginTop: 16, textAlign: 'center' }}>Activity on this portal is monitored by FinShield</div>
      </form></div></div>
  );
  if (!session.groups.includes('Staff')) return (
    <div className="main" style={{ minHeight: '100vh' }}>
      <div className="top"><div><h1>FinLend Ops</h1><div className="sub">Staff portal · SAMPLE data</div></div><span className="sp" />
        <div className="live">● {session.email}</div><button className="btn ghost" onClick={logout}>⎋ Sign out</button></div>
      <div className="content"><div className="card"><div className="empty"><div className="big">🔒</div>FinLend Ops needs the Staff group. FinShield console users sign in to the FinShield dashboard instead.</div></div></div>
      <Footer />
    </div>
  );
  return <StaffShell>{children}</StaffShell>;
}
