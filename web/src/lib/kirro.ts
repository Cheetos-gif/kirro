// Typed server-side KIRRO Core calls. Every function here runs on the server only (Server
// Components, Route Handlers, Server Actions) — the browser never talks to KIRRO Core directly.
import { kirroApi, request } from '@/api';

export interface StateView {
  declaration_id: string;
  state: string;
  confirmed_fields: Record<string, unknown>;
  open_field: string | null;
  open_field_note: string | null;
  readback_presented: boolean;
  allowed_actions: string[];
  booking_ref: string | null;
}

export interface DeclarationFull {
  declaration_id: string;
  state: string;
  event_name: string | null;
  date: string | null;
  group_size: number | null;
  min_group_size: number | null;
  max_price_paise: number | null;
  hard_constraints: Record<string, unknown>;
  mandate_id: string | null;
  mandate_paise: number | null;
  hold_id: string | null;
  payment_id: string | null;
  booking_ref: string | null;
  slot_label: string | null;
  slot_price_paise: number | null;
  terminal_reason: string | null;
  field_notes: Record<string, string>;
}

export interface DecisionRecord {
  ts: string;
  run_id: string;
  seq: number;
  declaration_id: string | null;
  state_before: string | null;
  state_after: string | null;
  decision: string;
  decided_by: 'code' | 'llm';
  rule: string;
  action: string;
  connector: string | null;
  result: string;
  user_message: string | null;
}

export interface EvalVerdict {
  case_id?: string;
  passed?: boolean;
  [key: string]: unknown;
}

export interface EvalRunSummary {
  run_id: string;
  verdict: EvalVerdict;
}

export interface EvalRunDetail extends EvalRunSummary {
  log: DecisionRecord[];
  transcript: string;
}

export async function createDeclaration() {
  return request<StateView & { declaration_id: string }>({ method: 'POST', url: '/declarations' });
}

export async function setField(did: string, field: string, evidence: string, userText: string) {
  return request<Record<string, unknown>>({
    method: 'POST',
    url: `/declarations/${did}/fields`,
    data: { user_text: userText, field, evidence },
  });
}

export async function getReadback(did: string) {
  return request<Record<string, unknown>>({
    method: 'POST',
    url: `/declarations/${did}/readback`,
    data: {},
  });
}

export async function confirmReadback(did: string, confirmed: boolean) {
  return request<Record<string, unknown>>({
    method: 'POST',
    url: `/declarations/${did}/readback`,
    data: { text: confirmed ? 'yes' : 'no' },
  });
}

export async function authorise(did: string) {
  return request<Record<string, unknown>>({
    method: 'POST',
    url: `/declarations/${did}/authorise`,
  });
}

export async function getDeclarationState(did: string) {
  return request<StateView>({ method: 'GET', url: `/declarations/${did}` });
}

export async function listDeclarations() {
  return request<StateView[]>({ method: 'GET', url: '/declarations' });
}

export async function getDeclarationFull(did: string) {
  return request<DeclarationFull>({ method: 'GET', url: `/declarations/${did}/full` });
}

export async function getDecisionLog(declarationId?: string) {
  return request<DecisionRecord[]>({
    method: 'GET',
    url: '/log',
    params: declarationId ? { declaration_id: declarationId } : undefined,
  });
}

/** Last text the agent said for this declaration — e.g. the read-back summary or an open question. */
export async function getLatestUserMessage(did: string) {
  const log = await getDecisionLog(did);
  for (let i = log.length - 1; i >= 0; i--) {
    if (log[i].decision === 'message_to_user' && log[i].user_message) return log[i].user_message;
  }
  return null;
}

export async function listEvalRuns() {
  return request<EvalRunSummary[]>({ method: 'GET', url: '/evals/runs' });
}

export async function getEvalRun(runId: string) {
  return request<EvalRunDetail>({ method: 'GET', url: `/evals/runs/${runId}` });
}

export async function kirroHealth() {
  const res = await kirroApi.get<{ status: string; service: string; run_id: string }>('/health');
  return res.data;
}
