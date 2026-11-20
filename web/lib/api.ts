/**
 * Typed FinShield API client. Source of truth: contract/openapi.yaml and contract/schemas/*.
 *
 * - Live mode: NEXT_PUBLIC_API_URL (already includes /v1) + Cognito ID token from setTokenProvider().
 * - Mock mode: NEXT_PUBLIC_USE_MOCKS=true reads contract/fixtures/*.json, no network.
 *
 * Every response is the envelope {data, error}; this client unwraps it and throws ApiError on error.
 * All sample data is synthetic (SAMPLE). DPDP-aligned readiness and controls.
 */

// ---------------------------------------------------------------- types (mirror contract/schemas)

export type Severity = 'CRITICAL' | 'HIGH' | 'MEDIUM';
export type AlertStatus = 'OPEN' | 'CONTAINED' | 'AWAITING_APPROVAL' | 'LOCKED' | 'RELEASED' | 'CLOSED';
export type DataClass = 'KYC' | 'FINANCIAL' | 'PII' | 'NONE';
export type CognitoGroup = 'Analyst' | 'SecurityHead' | 'ComplianceHead' | 'Auditor' | 'Admin';

export interface Signal {
  code: string; // S1..S11
  points: number;
  facts: Record<string, unknown>;
}
export interface Deadline {
  body: 'RBI' | 'CERT-In' | 'DPB';
  due_at: string;
}
export interface ContainmentAction {
  action: string;
  mode: 'LIVE' | 'DRY_RUN';
  result: string;
  at: string;
  detail?: string | Record<string, unknown> | null;
}
export interface AiExplanation {
  headline: string;
  summary: string;
  why_unusual: string[];
  rules_affected: { regulation: string; clause: string; why: string }[];
  root_cause_hypotheses: string[];
  affected_assets: string[];
  recommended_actions: string[];
  confidence: 'high' | 'medium' | 'low';
  confidence_reason: string;
  numbers_used: Record<string, number>;
}
export interface Alert {
  alert_id: string;
  user_id: string;
  principal_arn: string | null;
  score: number;
  severity: Severity;
  status: AlertStatus;
  signals: Signal[];
  exceptions_applied: string[];
  customers_affected: number;
  data_classes: DataClass[];
  event_ids: string[];
  detected_at: string;
  window_start: string;
  scenario_id: string | null;
  deadlines: Deadline[];
  containment: ContainmentAction[];
  ai: AiExplanation | null;
  ai_status: 'PENDING' | 'OK' | 'FALLBACK';
  execution_arn: string | null;
}
export interface FinShieldEvent {
  event_id: string;
  ts: string;
  source: 'simulator' | 'cloudtrail' | 'guardduty' | 'config' | 'app';
  scenario_id?: string | null;
  is_replay?: boolean | null;
  user_id: string;
  principal_arn?: string | null;
  action: string;
  object_id?: string | null;
  customer_id?: string | null;
  data_class?: DataClass | null;
  purpose?: string | null;
  bytes?: number | null;
  amount_inr?: number | null;
  ip?: string | null;
  city?: string | null;
  device_id?: string | null;
  role?: string | null;
  destination?: string | null;
  resource_arn?: string | null;
  raw_ref?: string | null;
}
export interface EvidenceEntry {
  alert_id: string;
  seq: number;
  ts: string;
  type: string;
  actor: string;
  payload: Record<string, unknown>;
  prev_hash: string;
  hash: string;
}
export interface Report {
  alert_id: string;
  report_type: 'RBI_INCIDENT' | 'CERTIN_FORM' | 'DPB_NOTICE' | 'CUSTOMER_NOTICE';
  status: 'PENDING' | 'DRAFT' | 'FALLBACK' | 'FAILED';
  body_md: string;
  model_id: string;
  generated_at: string;
}
export interface VerifyResult {
  valid: boolean;
  broken_at_seq: number | null;
}
export type ControlState = 'COMPLIANT' | 'NON_COMPLIANT' | 'NOT_APPLICABLE' | 'UNKNOWN';
export interface ControlStatus {
  control_id: string;
  source: 'config' | 'guardduty' | 'internal';
  status: ControlState;
  resource_arn: string | null;
  last_evaluated: string;
}
export interface DeadlineDue {
  alert_id: string;
  body: Deadline['body'];
  due_at: string;
  seconds_remaining: number;
}
export interface Posture {
  posture_score: number;
  alerts_by_severity: Record<Severity, number>;
  config_results: ControlStatus[];
  consent_risks: { purpose_mismatches: number; withdrawn_consents_accessed: number };
  deadlines_due_soon: DeadlineDue[];
}
export interface Baseline {
  p95_15min: number;
  avg_daily: number;
  usual_hours: string;
  cities: string[];
  devices: string[];
  p95_disburse_inr: number | null;
}
export interface UserProfile {
  user_id: string;
  name_pseudo: string;
  team: string;
  role: string;
  is_admin: boolean;
  is_service: boolean;
  office_start?: string;
  office_end?: string;
  home_city?: string;
  devices?: string[];
  partner_id?: string | null;
  iam_principal_arn?: string | null;
  baseline: Baseline;
  recent_risk: { alert_id: string; score: number; severity: Severity; detected_at: string }[];
}
/** contract/config.json */
export interface RulesConfig {
  version: string;
  timezone_offset: string;
  score_cap: number;
  incident_window_minutes: number;
  severity_thresholds: Record<Severity, number>;
  deadlines: { body: string; hours: number; label: string }[];
  signals: Record<string, Record<string, unknown>>;
  exceptions: Record<string, Record<string, unknown>>;
}
export interface ComplianceControl {
  control_id: string;
  obligation: string;
  finshield_control: string;
  evidence: string;
  screen: string;
  status: 'IN_PLACE' | 'GAP' | 'NOT_APPLICABLE' | 'UNKNOWN';
  verify_clause?: boolean;
}
export interface Privacy {
  consent_risks: { customer_id: string; issue: string }[];
  unmasked_aadhaar_files: { file_id: string; customer_id: string; doc_type: string }[];
  purpose_mismatches: { alert_id: string; user_id: string; purpose: string; customers: number }[];
}
export interface ApprovalInput {
  type: 'TICKET' | 'SCHEDULED_JOB';
  subject_id: string;
  max_files?: number | null;
  data_class?: DataClass;
  valid_from: string;
  valid_to: string;
  approver_id?: string;
  job_id?: string | null;
}
export interface Approval extends ApprovalInput {
  approval_id: string;
}
export interface AccuracyRow {
  scenario_id: string;
  expected_level: Severity | 'LOGGED';
  actual_level: Severity | 'LOGGED';
  expected_score: number;
  actual_score: number;
  pass: boolean;
  time_to_alert_ms: number | null;
}
export interface AccuracyResult {
  run_id: string;
  ran_at: string;
  passed: number;
  total: number;
  false_alerts_normal_days: number;
  rows: AccuracyRow[];
}
export interface DecisionResult {
  alert_id: string;
  decision: 'APPROVE' | 'REJECT';
  status: AlertStatus;
}
export interface ReleaseResult {
  alert_id: string;
  status: AlertStatus;
  released: { action: string; mode: 'LIVE' | 'DRY_RUN'; result: string }[];
}
export interface SimulateResult {
  accepted: boolean;
  scenario_id: string | null;
  events_sent: number;
}
export interface AskResult {
  answer: string;
  sources: string[];
  ai_status?: 'OK' | 'FALLBACK';
}
export interface AlertFilter {
  status?: AlertStatus;
  severity?: Severity;
}

export class ApiError extends Error {
  constructor(public code: string, message: string, public httpStatus?: number) {
    super(message);
    this.name = 'ApiError';
  }
}

interface Envelope<T> {
  data: T | null;
  error: { code: string; message: string } | null;
}

// ---------------------------------------------------------------- config

export const useMocks = (): boolean => process.env.NEXT_PUBLIC_USE_MOCKS === 'true';
const baseUrl = (): string => (process.env.NEXT_PUBLIC_API_URL ?? '').replace(/\/+$/, '');

type TokenProvider = () => Promise<string | null> | string | null;
let tokenProvider: TokenProvider = () => null;
/** Call once after Cognito sign-in: setTokenProvider(() => session.getIdToken().getJwtToken()). */
export function setTokenProvider(fn: TokenProvider): void {
  tokenProvider = fn;
}

// ---------------------------------------------------------------- mock mode (contract/fixtures)

const FIXTURES = {
  posture: () => import('../../contract/fixtures/api_posture.json'),
  alerts: () => import('../../contract/fixtures/api_alerts_list.json'),
  alert: () => import('../../contract/fixtures/api_alert_detail.json'),
  timeline: () => import('../../contract/fixtures/api_alert_timeline.json'),
  evidence: () => import('../../contract/fixtures/api_alert_evidence.json'),
  verify: () => import('../../contract/fixtures/api_evidence_verify.json'),
  tamper: () => import('../../contract/fixtures/api_evidence_tamper_demo.json'),
  decision: () => import('../../contract/fixtures/api_decision.json'),
  release: () => import('../../contract/fixtures/api_release.json'),
  reports: () => import('../../contract/fixtures/api_reports.json'),
  ask: () => import('../../contract/fixtures/api_ask.json'),
  user: () => import('../../contract/fixtures/api_user.json'),
  rules: () => import('../../contract/fixtures/api_rules.json'),
  compliance: () => import('../../contract/fixtures/api_compliance.json'),
  privacy: () => import('../../contract/fixtures/api_privacy.json'),
  approvals: () => import('../../contract/fixtures/api_approvals_list.json'),
  approvalCreated: () => import('../../contract/fixtures/api_approvals_create.json'),
  simulate: () => import('../../contract/fixtures/api_simulate.json'),
  accuracyRun: () => import('../../contract/fixtures/api_accuracy_run.json'),
  accuracy: () => import('../../contract/fixtures/api_accuracy.json'),
} as const;

async function fixture<T>(name: keyof typeof FIXTURES): Promise<T> {
  const mod = (await FIXTURES[name]()) as unknown as { default: Envelope<T> };
  const env = JSON.parse(JSON.stringify(mod.default)) as Envelope<T>; // fresh copy; callers may mutate
  return env.data as T;
}

/** In-memory state so mock mode can show approve and release. */
const mockState: { status?: AlertStatus } = {};
async function mockAlert(): Promise<Alert> {
  const a = await fixture<Alert>('alert');
  if (mockState.status) a.status = mockState.status;
  return a;
}

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
    throw new ApiError(env?.error?.code ?? `HTTP_${res.status}`, env?.error?.message ?? res.statusText, res.status);
  }
  return env.data as T;
}

const qs = (params: Record<string, string | undefined>): string => {
  const p = Object.entries(params).filter(([, v]) => v);
  return p.length ? '?' + new URLSearchParams(p as [string, string][]).toString() : '';
};
const enc = encodeURIComponent;

// ---------------------------------------------------------------- client (one method per openapi operationId)

export const api = {
  getPosture: (): Promise<Posture> => (useMocks() ? fixture('posture') : request('GET', '/posture')),

  listAlerts: async (f: AlertFilter = {}): Promise<Alert[]> => {
    if (!useMocks()) return request('GET', `/alerts${qs({ status: f.status, severity: f.severity })}`);
    const all = (await fixture<Alert[]>('alerts')).map((a) => (mockState.status ? { ...a, status: mockState.status } : a));
    return all.filter((a) => (!f.status || a.status === f.status) && (!f.severity || a.severity === f.severity));
  },

  getAlert: (id: string): Promise<Alert> => (useMocks() ? mockAlert() : request('GET', `/alerts/${enc(id)}`)),
  getAlertTimeline: (id: string): Promise<FinShieldEvent[]> => (useMocks() ? fixture('timeline') : request('GET', `/alerts/${enc(id)}/timeline`)),
  getEvidence: (id: string): Promise<EvidenceEntry[]> => (useMocks() ? fixture('evidence') : request('GET', `/alerts/${enc(id)}/evidence`)),
  verifyEvidence: (id: string): Promise<VerifyResult> => (useMocks() ? fixture('verify') : request('POST', `/alerts/${enc(id)}/evidence/verify`)),
  tamperDemo: (id: string): Promise<VerifyResult> => (useMocks() ? fixture('tamper') : request('POST', `/alerts/${enc(id)}/evidence/tamper-demo`)),

  decideAlert: async (id: string, decision: 'APPROVE' | 'REJECT', reason: string): Promise<DecisionResult> => {
    if (!useMocks()) return request('POST', `/alerts/${enc(id)}/decision`, { decision, reason });
    mockState.status = decision === 'APPROVE' ? 'LOCKED' : 'CONTAINED';
    return { alert_id: id, decision, status: mockState.status };
  },
  releaseAlert: async (id: string): Promise<ReleaseResult> => {
    if (!useMocks()) return request('POST', `/alerts/${enc(id)}/release`);
    mockState.status = 'RELEASED';
    return fixture('release');
  },

  getReports: (id: string): Promise<Report[]> => (useMocks() ? fixture('reports') : request('GET', `/alerts/${enc(id)}/reports`)),
  askFinShield: (id: string, question: string): Promise<AskResult> => (useMocks() ? fixture('ask') : request('POST', `/alerts/${enc(id)}/ask`, { question })),

  getUser: (id: string): Promise<UserProfile> => (useMocks() ? fixture('user') : request('GET', `/users/${enc(id)}`)),
  getRules: (): Promise<RulesConfig> => (useMocks() ? fixture('rules') : request('GET', '/rules')),
  getCompliance: (): Promise<ComplianceControl[]> => (useMocks() ? fixture('compliance') : request('GET', '/compliance')),
  getPrivacy: (): Promise<Privacy> => (useMocks() ? fixture('privacy') : request('GET', '/privacy')),

  listApprovals: (): Promise<Approval[]> => (useMocks() ? fixture('approvals') : request('GET', '/approvals')),
  createApproval: (input: ApprovalInput): Promise<Approval> => (useMocks() ? fixture('approvalCreated') : request('POST', '/approvals', input)),

  simulate: (body: { scenario_id?: string; guardduty_sample?: boolean; reset?: boolean }): Promise<SimulateResult> =>
    useMocks() ? fixture('simulate') : request('POST', '/simulate', body),

  runAccuracy: (): Promise<AccuracyResult> => (useMocks() ? fixture('accuracyRun') : request('POST', '/accuracy/run')),
  getAccuracy: (): Promise<AccuracyResult> => (useMocks() ? fixture('accuracy') : request('GET', '/accuracy')),
};

export type Api = typeof api;

/** Which buttons a Cognito group may use (mirrors x-groups in openapi.yaml; the API enforces it too). */
export const can = {
  decide: (groups: CognitoGroup[]) => groups.some((g) => g === 'SecurityHead' || g === 'ComplianceHead'),
  release: (groups: CognitoGroup[]) => groups.includes('SecurityHead'),
  ask: (groups: CognitoGroup[]) => groups.some((g) => g !== 'Auditor'),
  admin: (groups: CognitoGroup[]) => groups.includes('Admin'),
  approvals: (groups: CognitoGroup[]) => groups.includes('SecurityHead'),
};
