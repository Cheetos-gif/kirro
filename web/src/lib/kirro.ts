// Typed server-side KIRRO Core calls. Every function here runs on the server only (Server
// Components, Route Handlers, Server Actions) — the browser never talks to KIRRO Core directly.
//
// Read paths are schema-validated: a response that does not match what the UI expects throws
// (surfaced by the error boundary) instead of silently rendering `undefined`. Mutation paths stay
// loosely typed because the engine's reply shape varies by outcome and the wizard reads it defensively.
import * as z from 'zod';

import { kirroApi, request } from '@/api';

// `state_view()` on the backend (agent/tools/toolset.py) never includes `declaration_id` or
// `booking_ref` — those are added per-endpoint. GET /declarations/{id} returns this shape bare;
// POST /declarations adds `declaration_id`; GET /declarations adds both. Three schemas, not one,
// because validating against a shape the endpoint cannot return is the bug this file exists to catch.
const stateViewSchema = z.object({
  state: z.string(),
  confirmed_fields: z.record(z.string(), z.unknown()),
  open_field: z.string().nullable(),
  open_field_note: z.string().nullable(),
  readback_presented: z.boolean(),
  allowed_actions: z.array(z.string()),
});
const createdDeclarationSchema = stateViewSchema.extend({ declaration_id: z.string() });
const listedDeclarationSchema = createdDeclarationSchema.extend({
  booking_ref: z.string().nullable(),
});

const declarationFullSchema = z.object({
  declaration_id: z.string(),
  state: z.string(),
  event_id: z.string().nullable(),
  event_name: z.string().nullable(),
  fulfilment: z.string(),
  date: z.string().nullable(),
  group_size: z.number().nullable(),
  min_group_size: z.number().nullable(),
  max_price_paise: z.number().nullable(),
  hard_constraints: z.record(z.string(), z.unknown()),
  alternatives: z.array(z.string()),
  language: z.string(),
  open_field: z.string().nullable(),
  readback_presented: z.boolean(),
  confirmed_by_user: z.boolean(),
  mandate_id: z.string().nullable(),
  mandate_paise: z.number().nullable(),
  release_id: z.string().nullable(),
  slot_id: z.string().nullable(),
  slot_label: z.string().nullable(),
  slot_time: z.string().nullable(),
  allocated_group_size: z.number().nullable(),
  slot_price_paise: z.number().nullable(),
  hold_id: z.string().nullable(),
  payment_id: z.string().nullable(),
  booking_ref: z.string().nullable(),
  shipment_waybill: z.string().nullable(),
  failed_slots: z.array(z.string()),
  terminal_reason: z.string().nullable(),
  field_notes: z.record(z.string(), z.string()),
  hold_released: z.boolean(),
  mandate_released: z.boolean(),
  // Kept (not stripped) so the endpoint's stated purpose — every field, including connector
  // provenance — survives validation. ConnectorResult is not modelled deeply; nothing reads it yet.
  user_id: z.string(),
  inventory_result: z.unknown(),
  payment_result: z.unknown(),
  processed_event_ids: z.array(z.string()),
  allocations_last_30d: z.number(),
});

const decisionRecordSchema = z.object({
  ts: z.string(),
  run_id: z.string(),
  seq: z.number(),
  declaration_id: z.string().nullable(),
  state_before: z.string().nullable(),
  state_after: z.string().nullable(),
  decision: z.string(),
  decided_by: z.enum(['code', 'llm']),
  rule: z.string(),
  action: z.string(),
  connector: z.string().nullable(),
  result: z.string(),
  user_message: z.string().nullable(),
});

const evalCheckSchema = z.object({
  name: z.string(),
  passed: z.boolean(),
  detail: z.string(),
  builtin: z.boolean(),
});

const evalVerdictSchema = z.object({
  run_id: z.string(),
  case: z.string(),
  name: z.string(),
  mode: z.string(),
  policy: z.string(),
  prompt_version: z.string(),
  passed: z.boolean(),
  final_state: z.string(),
  checks: z.array(evalCheckSchema),
});

const evalRunSummarySchema = z.object({
  run_id: z.string(),
  verdict: evalVerdictSchema,
});

const evalRunDetailSchema = evalRunSummarySchema.extend({
  log: z.array(decisionRecordSchema),
  transcript: z.string(),
});

export type StateView = z.infer<typeof stateViewSchema>;
export type CreatedDeclaration = z.infer<typeof createdDeclarationSchema>;
export type DeclarationSummary = z.infer<typeof listedDeclarationSchema>;
export type DeclarationFull = z.infer<typeof declarationFullSchema>;
export type DecisionRecord = z.infer<typeof decisionRecordSchema>;
export type EvalCheck = z.infer<typeof evalCheckSchema>;
export type EvalRunSummary = z.infer<typeof evalRunSummarySchema>;
export type EvalRunDetail = z.infer<typeof evalRunDetailSchema>;
export type EvalVerdict = EvalRunSummary['verdict'];

export async function createDeclaration() {
  return request({ method: 'POST', url: '/declarations', schema: createdDeclarationSchema });
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
  return request({ method: 'GET', url: `/declarations/${did}`, schema: stateViewSchema });
}

export async function listDeclarations() {
  return request({ method: 'GET', url: '/declarations', schema: z.array(listedDeclarationSchema) });
}

export async function getDeclarationFull(did: string) {
  return request({
    method: 'GET',
    url: `/declarations/${did}/full`,
    schema: declarationFullSchema,
  });
}

export async function getDecisionLog(declarationId?: string) {
  return request({
    method: 'GET',
    url: '/log',
    params: declarationId ? { declaration_id: declarationId } : undefined,
    schema: z.array(decisionRecordSchema),
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
  return request({ method: 'GET', url: '/evals/runs', schema: z.array(evalRunSummarySchema) });
}

export async function getEvalRun(runId: string) {
  return request({ method: 'GET', url: `/evals/runs/${runId}`, schema: evalRunDetailSchema });
}

export async function kirroHealth() {
  const res = await kirroApi.get<{ status: string; service: string; run_id: string }>('/health');
  return res.data;
}
