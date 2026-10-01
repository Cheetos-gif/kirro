'use server';

import {
  authorise,
  confirmReadback,
  createDeclaration,
  getDeclarationFull,
  getDeclarationState,
  getLatestUserMessage,
  getReadback,
  setField,
} from '@/lib/kirro';
import type { CreatedDeclaration, DeclarationFull, StateView } from '@/lib/kirro';

export interface DeclareFields {
  event: string;
  date: string;
  group_size: string;
  max_price: string;
  min_group_size?: string;
  time_window?: string;
}

export async function startDeclaration(): Promise<CreatedDeclaration> {
  return createDeclaration();
}

/**
 * Submits every non-empty field in the user's own words — the same `evidence` the voice agent
 * would pass to `set_field`. Code parses it; the web form never sends a pre-parsed value.
 */
export async function submitFields(did: string, fields: DeclareFields): Promise<StateView> {
  const order: Array<keyof DeclareFields> = [
    'event',
    'date',
    'group_size',
    'max_price',
    'min_group_size',
    'time_window',
  ];
  for (const key of order) {
    const value = fields[key];
    if (!value) continue;
    await setField(did, key, value, value);
  }
  return getDeclarationState(did);
}

export async function requestReadback(
  did: string
): Promise<{ state: StateView; text: string | null }> {
  await getReadback(did);
  const [state, text] = await Promise.all([getDeclarationState(did), getLatestUserMessage(did)]);
  return { state, text };
}

export async function respondReadback(did: string, confirmed: boolean): Promise<StateView> {
  await confirmReadback(did, confirmed);
  return getDeclarationState(did);
}

export async function doAuthorise(did: string): Promise<DeclarationFull> {
  await authorise(did);
  return getDeclarationFull(did);
}
