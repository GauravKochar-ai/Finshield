'use client';
/** Cognito sign-in (USER_PASSWORD_AUTH over the public Cognito endpoint, no SDK) + mock-mode role switcher. */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { setTokenProvider, useMocks, type CognitoGroup } from './api';

export interface Session {
  email: string;
  name: string;
  groups: CognitoGroup[];
}
interface Tokens { idToken: string; refreshToken?: string; expiresAt: number }

export const MOCK_ROLES: CognitoGroup[] = ['Admin', 'SecurityHead', 'ComplianceHead', 'Analyst', 'Auditor'];
const KEY = 'fs_tokens';
const REGION = process.env.NEXT_PUBLIC_REGION ?? 'ap-south-1';
const CLIENT_ID = process.env.NEXT_PUBLIC_USER_POOL_CLIENT_ID ?? '';

async function cognito(target: string, body: unknown): Promise<any> {
  const res = await fetch(`https://cognito-idp.${REGION}.amazonaws.com/`, {
    method: 'POST',
    headers: { 'content-type': 'application/x-amz-json-1.1', 'x-amz-target': `AWSCognitoIdentityProviderService.${target}` },
    body: JSON.stringify(body),
  });
  const j = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(j.message || j.__type || `Sign-in failed (HTTP ${res.status})`);
  return j;
}

function decode(idToken: string): { email: string; name: string; groups: CognitoGroup[] } {
  const p = JSON.parse(atob(idToken.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
  const email = p.email || p['cognito:username'] || '';
  return { email, name: p.name || email.split('@')[0], groups: (p['cognito:groups'] ?? []) as CognitoGroup[] };
}

function fromResult(r: any, prevRefresh?: string): Tokens {
  return { idToken: r.IdToken, refreshToken: r.RefreshToken ?? prevRefresh, expiresAt: Date.now() + (r.ExpiresIn ?? 3600) * 1000 };
}
const load = (): Tokens | null => {
  try { return JSON.parse(sessionStorage.getItem(KEY) || 'null'); } catch { return null; }
};

interface AuthCtx {
  session: Session | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  mockRole: CognitoGroup;
  setMockRole: (r: CognitoGroup) => void;
}
const Ctx = createContext<AuthCtx>(null as never);
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const mocks = useMocks();
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [mockRole, setMockRoleState] = useState<CognitoGroup>('Admin');

  const logout = useCallback(() => {
    sessionStorage.removeItem(KEY);
    setSession(null);
  }, []);

  useEffect(() => {
    if (mocks) {
      const r = (localStorage.getItem('fs_mock_role') as CognitoGroup) || 'Admin';
      setMockRoleState(r);
      setSession({ email: 'demo@finlend.demo', name: 'Demo user', groups: [r] });
      setReady(true);
      return;
    }
    setTokenProvider(async () => {
      let t = load();
      if (t && t.expiresAt - Date.now() < 60_000 && t.refreshToken) {
        try {
          const r = await cognito('InitiateAuth', { AuthFlow: 'REFRESH_TOKEN_AUTH', ClientId: CLIENT_ID, AuthParameters: { REFRESH_TOKEN: t.refreshToken } });
          t = fromResult(r.AuthenticationResult, t.refreshToken);
          sessionStorage.setItem(KEY, JSON.stringify(t));
        } catch { /* the API call will 401 and sign the user out */ }
      }
      return t?.idToken ?? null;
    });
    const t = load();
    if (t && t.expiresAt > Date.now()) setSession(decode(t.idToken));
    setReady(true);
  }, [mocks]);

  const login = useCallback(async (email: string, password: string) => {
    if (!CLIENT_ID) throw new Error('NEXT_PUBLIC_USER_POOL_CLIENT_ID is not set. Run `make env` or use NEXT_PUBLIC_USE_MOCKS=true.');
    const r = await cognito('InitiateAuth', { AuthFlow: 'USER_PASSWORD_AUTH', ClientId: CLIENT_ID, AuthParameters: { USERNAME: email, PASSWORD: password } });
    if (r.ChallengeName) throw new Error(`Cognito requires "${r.ChallengeName}". Set a permanent password first (admin-set-user-password).`);
    const t = fromResult(r.AuthenticationResult);
    sessionStorage.setItem(KEY, JSON.stringify(t));
    setSession(decode(t.idToken));
  }, []);

  const setMockRole = useCallback((r: CognitoGroup) => {
    localStorage.setItem('fs_mock_role', r);
    setMockRoleState(r);
    setSession({ email: 'demo@finlend.demo', name: 'Demo user', groups: [r] });
  }, []);

  const value = useMemo(() => ({ session, ready, login, logout, mockRole, setMockRole }), [session, ready, login, logout, mockRole, setMockRole]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
