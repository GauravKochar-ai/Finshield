'use client';
import { useEffect, useState } from 'react';
import { api } from './api';
import { cleanRole } from './format';

const names = new Map<string, string>(); // user_id -> display name ('' = unknown)
export const isUnmapped = (uid: string) => uid.startsWith('unmapped:');

/** "unmapped:arn:aws:sts::123:assumed-role/finshield-dev-KycLabelFunctionRole-xxx/session" -> "Kyc Label Function" */
export function systemName(uid: string): string {
  const m = uid.match(/(?:assumed-role|role|user)\/([^/]+)/);
  return m ? cleanRole(m[1]) || 'System role' : 'Unknown identity';
}

export interface Who { name: string; sub: string; system: boolean }

/** Resolves user ids to display names (one cached getUser each). Unmapped cloud roles are shown as system roles. */
export function useWho(ids: string[]): (uid: string) => Who {
  const [, tick] = useState(0);
  const key = [...new Set(ids)].sort().join(',');
  useEffect(() => {
    const todo = key.split(',').filter((i) => i && !isUnmapped(i) && !names.has(i));
    if (!todo.length) return;
    Promise.all(todo.map((i) => api.getUser(i).then((u) => names.set(i, u.name_pseudo)).catch(() => names.set(i, '')))).then(() => tick((t) => t + 1));
  }, [key]);
  return (uid: string): Who => {
    if (isUnmapped(uid)) return { name: systemName(uid), sub: 'System role, not linked to a person', system: true };
    const n = names.get(uid);
    return n ? { name: n, sub: uid, system: false } : { name: uid, sub: '', system: false };
  };
}

const aliasCache = new Map<string, string>();
const alias = async (uid: string): Promise<string | null> => {
  if (!globalThis.crypto?.subtle) return null;
  const d = await crypto.subtle.digest('SHA-1', new TextEncoder().encode(uid));
  return 'User-' + [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, '0')).join('').slice(0, 4).toUpperCase();
};

/** The AI is given a pseudonym ("User-7B62") instead of the identity. Swap it back to the name shown everywhere else. */
export function useDeidentify(uids: string[]): (text: string, uid: string, display: string) => string {
  const [, tick] = useState(0);
  const key = [...new Set(uids)].sort().join(',');
  useEffect(() => {
    const todo = key.split(',').filter((u) => u && !aliasCache.has(u));
    if (!todo.length) return;
    Promise.all(todo.map(async (u) => { const a = await alias(u); if (a) aliasCache.set(u, a); })).then(() => tick((t) => t + 1));
  }, [key]);
  return (text, uid, display) => { const a = aliasCache.get(uid); return a && text ? text.split(a).join(display) : text; };
}
