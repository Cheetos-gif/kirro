import * as z from 'zod';

import { request } from '@/api';
import { env } from '@/env';

import * as s from './schemas';

/**
 * Typed calls against `mock_server` (docs/connectors.md). Server-side only: the axios client in `@/api` reads
 * `MOCK_API_URL` from server env and attaches the `X-Run-Id` correlation header.
 */

export async function listEvents(filters: { organiser_id?: string; status?: string } = {}) {
  const body = await request({
    url: '/venue/catalogue',
    params: filters,
    schema: z.object({ events: z.array(s.eventSchema) }),
  });
  return body.events;
}

export async function listReleases(filters: { event_id?: string; date?: string } = {}) {
  const body = await request({
    url: '/venue/releases',
    params: filters,
    schema: z.object({ releases: z.array(s.releaseSummarySchema) }),
  });
  return body.releases;
}

export function getRelease(releaseId: string) {
  return request({ url: `/venue/releases/${releaseId}`, schema: s.releaseDetailSchema });
}

export async function listOrganisers(status?: 'pending' | 'approved') {
  const body = await request({
    url: '/venue/organisers',
    params: status ? { status } : {},
    schema: z.object({ organisers: z.array(s.organiserSchema) }),
  });
  return body.organisers;
}

export function createOrganiser(input: { name: string; contact: string; requested_by: string }) {
  return request({
    method: 'POST',
    url: '/venue/organisers',
    data: input,
    schema: s.organiserSchema,
  });
}

export function approveOrganiser(organiserId: string) {
  return request({
    method: 'POST',
    url: `/venue/organisers/${organiserId}/approve`,
    schema: s.organiserSchema,
  });
}

export function createEvent(input: {
  name: string;
  organiser_id: string;
  status?: 'draft' | 'published';
  fulfilment?: string;
}) {
  return request({ method: 'POST', url: '/venue/events', data: input, schema: s.eventSchema });
}

export function patchEvent(
  eventId: string,
  input: { name?: string; status?: 'draft' | 'published'; fulfilment?: string }
) {
  return request({
    method: 'PATCH',
    url: `/venue/events/${eventId}`,
    data: input,
    schema: s.eventSchema,
  });
}

export function createRelease(input: {
  event_id: string;
  date: string;
  opens_at: string;
  allocation_mode: s.AllocationMode;
  slots: Array<{
    label: string;
    starts_at: string;
    capacity: number;
    price_per_person_paise: number;
  }>;
}) {
  return request({
    method: 'POST',
    url: '/venue/releases',
    data: input,
    schema: s.releaseDetailSchema,
  });
}

export function listDeclarations(releaseId: string) {
  return request({
    url: `/venue/releases/${releaseId}/declarations`,
    schema: z.object({ release_id: z.string(), declarations: z.array(s.declarationSchema) }),
  });
}

export function getUserProfile(userContact: string) {
  return request({
    url: `/venue/users/${encodeURIComponent(userContact)}/profile`,
    schema: s.userProfileSchema,
  });
}

export function setUserProfile(userContact: string, notifyPhone: string) {
  return request({
    method: 'PUT',
    url: `/venue/users/${encodeURIComponent(userContact)}/profile`,
    data: { notify_phone: notifyPhone },
    schema: s.userProfileSchema,
  });
}

export function declareInterest(
  releaseId: string,
  input: {
    user_contact: string;
    notify_phone: string;
    mandate_id?: string;
    acceptable_slot_ids: string[];
    group_size: number;
    min_group_size: number;
    max_price_paise: number;
  }
) {
  return request({
    method: 'POST',
    url: `/venue/releases/${releaseId}/declarations`,
    data: input,
    schema: z.object({ declaration_id: z.string(), release_id: z.string(), status: z.string() }),
  });
}

export function createMandate(amountPaise: number) {
  return request({
    method: 'POST',
    url: '/pinelabs/mandates',
    data: { amount: { value: amountPaise, currency: 'INR' } },
    schema: s.mandateSchema,
  });
}

export function buyRelease(
  releaseId: string,
  input: { slot_id: string; quantity: number; mandate_id: string; user_contact: string }
) {
  return request({
    method: 'POST',
    url: `/venue/releases/${releaseId}/buy`,
    data: input,
    schema: s.buyResultSchema,
  });
}

export function adminState(userContact?: string) {
  return request({
    url: '/__admin/state',
    params: { run_id: env.MOCK_RUN_ID, ...(userContact ? { user_contact: userContact } : {}) },
    schema: s.adminStateSchema,
  });
}

export function setScenario(input: {
  target: string;
  scenario?: string;
  sequence?: string[];
  delay_s?: number;
}) {
  return request({
    method: 'POST',
    url: '/__admin/scenario',
    data: { run_id: env.MOCK_RUN_ID, ...input },
    schema: z.object({ ok: z.boolean() }),
  });
}

export function resetRun() {
  return request({
    method: 'POST',
    url: '/__admin/reset',
    data: { run_id: env.MOCK_RUN_ID },
    schema: z.object({ ok: z.boolean() }),
  });
}
