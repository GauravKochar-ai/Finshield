'use client';
import { useState, type FormEvent, type ReactNode } from 'react';
import { useMocks } from '@/lib/api';
import { useAuth } from '@/lib/auth';

/** Sign-in gate. Only the Admin group may call POST /simulate. */
export function Gate({ children }: { children: ReactNode }) {
  const { session, ready, login, logout } = useAuth();
  const mocks = useMocks();
  const [email, setEmail] = useState(''), [pw, setPw] = useState(''), [err, setErr] = useState(''), [busy, setBusy] = useState(false);
  if (!ready) return null;
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(''); setBusy(true);
    try { await login(email, pw); } catch (x) { setErr(x instanceof Error ? x.message : String(x)); }
    setBusy(false);
  };
  if (!session) return (
    <div className="login" style={{ display: 'grid', gridTemplateColumns: '1fr' }}>
      <div className="form"><form onSubmit={submit}>
        <h2 style={{ margin: '0 0 4px' }}>FinShield Simulator</h2><div className="muted" style={{ marginBottom: 22 }}>Sign in as an Admin user</div>
        <label>Email</label><input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" required />
        <label>Password</label><input type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="current-password" required />
        <div className="err">{err}</div>
        <button className="btn primary" style={{ width: '100%', justifyContent: 'center', padding: 12 }} disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
      </form></div></div>
  );
  const isAdmin = session.groups.includes('Admin');
  return (
    <div className="main">
      <div className="top">
        <div><h1>FinShield Simulator</h1><div className="sub">Replay scenarios into the live pipeline. Separate app, synthetic data only.</div></div>
        <span className="sp" />
        <div className="live">{mocks ? '● Mock data' : `● ${session.email}`}</div>
        {!mocks && <button className="btn ghost" onClick={logout}>⎋ Sign out</button>}
      </div>
      <div className="content">{isAdmin ? children : <div className="card"><div className="empty"><div className="big">🔒</div>The simulator needs the Admin group.</div></div>}</div>
    </div>
  );
}
