/**
 * Typed client for the FinLend Ops staff API (/staff/* in contract/openapi.yaml, Cognito group Staff).
 *
 * - Live mode: NEXT_PUBLIC_API_URL (already includes /v1) + Cognito ID token from setTokenProvider().
 * - Mock mode: NEXT_PUBLIC_USE_MOCKS=true reads contract/fixtures/api_staff_*.json, no network.
 *
 * Every response is the envelope {data, error}; this client unwraps it and throws ApiError on error.
 * All customer data is synthetic (SAMPLE).
 */
// ---------------------------------------------------------------- types
export type Severity = 'CRITICAL' | 'HIGH' | 'MEDIUM';
export type CognitoGroup = 'Staff' | 'Analyst' | 'SecurityHead' | 'ComplianceHead' | 'Auditor' | 'Admin';
export type Purpose = 'loan_processing' | 'collections' | 'marketing' | 'audit' | 'registry_upload';
export const PURPOSES: Purpose[] = ['loan_processing', 'collections', 'marketing', 'audit', 'registry_upload'];
export type DocType = 'PAN' | 'AADHAAR' | 'SELFIE' | 'ADDRESS';
export const DOC_TYPES: DocType[] = ['PAN', 'AADHAAR', 'SELFIE', 'ADDRESS'];
export type UploadContentType = 'image/png' | 'image/jpeg';
export type Disposition = 'view' | 'download';

export interface StaffContainment {
  alert_id: string;
  status: 'CONTAINED' | 'AWAITING_APPROVAL' | 'LOCKED';
  mode: 'LIVE' | 'DRY_RUN';
}
export interface StaffMe {
  user_id: string;
  name_pseudo: string;
  team: string;
  role: string;
  access_scope: string;
  default_purpose: Purpose;
  containment: StaffContainment | null;
}
export interface StaffCustomerRow {
  customer_id: string;
  city: string;
  loan_id: string;
  assigned_agent: string | null;
  partner_id: string | null;
  aadhaar_masked: string;
  pan_fake: string;
  sample: boolean;
}
export interface KycFile {
  file_id: string;
  doc_type: DocType;
  size_kb: number;
  ai_label: string | null;
  unmasked_aadhaar_flag: boolean;
  available: boolean;
}
export interface StaffCustomer extends StaffCustomerRow {
  kyc_files: KycFile[];
  purpose_consented: boolean;
}
export interface StaffConsent {
  customer_id: string;
  purposes: string[];
  withdrawn: string[];
  given_at: string | null;
  notice_version: string | null;
  purpose: Purpose;
  purpose_consented: boolean;
  sample: boolean;
}
export interface StaffKycUrl {
  file_id: string;
  disposition: Disposition;
  url: string;
  expires_in: number;
}
export interface StaffKycUpload {
  file_id: string;
  s3_key: string;
  url: string;
  method: 'PUT';
  headers: Record<string, string>;
  expires_in: number;
}

export class ApiError extends Error {
  constructor(public code: string, message: string, public httpStatus?: number, public detail?: Record<string, unknown>) {
    super(message);
    this.name = 'ApiError';
  }
}
interface Envelope<T> {
  data: T | null;
  error: ({ code: string; message: string } & Record<string, unknown>) | null;
}

// ---------------------------------------------------------------- config
export const useMocks = (): boolean => process.env.NEXT_PUBLIC_USE_MOCKS === 'true';
const baseUrl = (): string => (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/+$/, '');

type TokenProvider = () => Promise<string | null> | string | null;
let tokenProvider: TokenProvider = () => null;
/** Called by AuthProvider after Cognito sign-in. */
export function setTokenProvider(fn: TokenProvider): void {
  tokenProvider = fn;
}

// ---------------------------------------------------------------- mock mode (contract/fixtures)
const FIXTURES = {
  me: () => import('../../contract/fixtures/api_staff_me.json'),
  customers: () => import('../../contract/fixtures/api_staff_customers.json'),
  customer: () => import('../../contract/fixtures/api_staff_customer.json'),
  consent: () => import('../../contract/fixtures/api_staff_consent.json'),
  kycUpload: () => import('../../contract/fixtures/api_staff_kyc_upload.json'),
  kycUrl: () => import('../../contract/fixtures/api_staff_kyc_url.json'),
} as const;

async function fixture<T>(name: keyof typeof FIXTURES): Promise<T> {
  const mod = (await FIXTURES[name]()) as unknown as { default: Envelope<T> };
  const env = JSON.parse(JSON.stringify(mod.default)) as Envelope<T>; // fresh copy; callers may mutate
  return env.data as T;
}

/** Tiny SAMPLE image so View works in mock mode without S3. */
const MOCK_IMG =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="420" height="260"><rect width="100%" height="100%" rx="16" fill="#16223d"/>' +
      '<text x="50%" y="46%" fill="#e7ecf6" font-family="sans-serif" font-size="22" text-anchor="middle">SAMPLE KYC document</text>' +
      '<text x="50%" y="60%" fill="#8e9ab5" font-family="sans-serif" font-size="14" text-anchor="middle">mock mode, synthetic data</text></svg>',
  );

// ---------------------------------------------------------------- live mode
async function request<T>(method: 'GET' | 'POST', path: string, body?: unknown): Promise<T> {
  const token = await tokenProvider();
  const res = await fetch(`${baseUrl()}${path}`, {
    method,
    headers: { 'content-type': 'application/json', ...(token ? { authorization: `Bearer ${token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  let env: Envelope<T> | null = null;
  try {
    env = (await res.json()) as Envelope<T>;
  } catch {
    /* non-JSON error body */
  }
  if (!res.ok || !env || env.error) {
    const e = env?.error;
    throw new ApiError(e?.code ?? `HTTP_${res.status}`, e?.message ?? res.statusText, res.status, e ?? undefined);
  }
  return env.data as T;
}

const qs = (params: Record<string, string | undefined>): string => {
  const p = Object.entries(params).filter(([, v]) => v);
  return p.length ? '?' + new URLSearchParams(p as [string, string][]).toString() : '';
};
const enc = encodeURIComponent;

// ---------------------------------------------------------------- client (one method per /staff operation)
export const api = {
  me: (): Promise<StaffMe> => (useMocks() ? fixture('me') : request('GET', '/staff/me')),
  customers: async (q: string | undefined, purpose: Purpose): Promise<StaffCustomerRow[]> => {
    if (!useMocks()) return request('GET', `/staff/customers${qs({ q: q || undefined, purpose })}`);
    const all = await fixture<StaffCustomerRow[]>('customers');
    return q ? all.filter((c) => c.customer_id === q) : all;
  },
  customer: async (id: string, purpose: Purpose): Promise<StaffCustomer> => {
    if (!useMocks()) return request('GET', `/staff/customers/${enc(id)}${qs({ purpose })}`);
    const c = await fixture<StaffCustomer>('customer');
    if (id === c.customer_id) return c;
    const row = (await fixture<StaffCustomerRow[]>('customers')).find((r) => r.customer_id === id);
    if (!row) throw new ApiError('NOT_FOUND', `Customer ${id} not found`, 404);
    return { ...c, ...row, kyc_files: c.kyc_files.map((f) => ({ ...f, file_id: f.file_id.replace(c.customer_id, id) })) };
  },
  consent: async (id: string, purpose: Purpose): Promise<StaffConsent> => {
    if (!useMocks()) return request('GET', `/staff/customers/${enc(id)}/consent${qs({ purpose })}`);
    const c = await fixture<StaffConsent>('consent');
    return { ...c, customer_id: id, purpose, purpose_consented: c.purposes.includes(purpose) && !c.withdrawn.includes(purpose) };
  },
  kycUrl: async (fileId: string, purpose: Purpose, disposition: Disposition): Promise<StaffKycUrl> => {
    if (!useMocks()) return request('POST', `/staff/kyc/${enc(fileId)}/url`, { purpose, disposition });
    const r = await fixture<StaffKycUrl>('kycUrl');
    return { ...r, file_id: fileId, disposition, url: MOCK_IMG };
  },
  kycUpload: async (cid: string, doc_type: DocType, purpose: Purpose, content_type: UploadContentType): Promise<StaffKycUpload> => {
    if (!useMocks()) return request('POST', `/staff/customers/${enc(cid)}/kyc-upload`, { doc_type, purpose, content_type });
    return fixture('kycUpload');
  },
};
export type Api = typeof api;
