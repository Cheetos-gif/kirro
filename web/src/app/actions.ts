'use server';

import { revalidatePath } from 'next/cache';

import { isApiError } from '@/api';
import { requireRole, requireViewer } from '@/lib/auth/roles';
import * as api from '@/lib/kirro/api';

export type ActionState = { ok: boolean; message: string } | null;

function messageOf(error: unknown): string {
  return isApiError(error) ? error.message : 'Something went wrong. Please try again.';
}

/** Form fields arrive as strings; `null` means the field was empty or not a number. */
function intField(formData: FormData, name: string): number | null {
  const raw = formData.get(name);
  if (typeof raw !== 'string' || raw.trim() === '') return null;
  const value = Number(raw);
  return Number.isFinite(value) ? Math.trunc(value) : null;
}

async function myOrganiserId(email: string): Promise<string | null> {
  const organisers = await api.listOrganisers();
  const mine = organisers.find(
    organiser =>
      organiser.status === 'approved' &&
      organiser.requested_by?.toLowerCase() === email.toLowerCase()
  );
  return mine?.organiser_id ?? null;
}

export async function declareAction(_prev: ActionState, formData: FormData): Promise<ActionState> {
  const viewer = await requireViewer();
  const releaseId = formData.get('release_id');
  if (typeof releaseId !== 'string') return { ok: false, message: 'Missing release.' };

  const groupSize = intField(formData, 'group_size');
  const minGroupSize = intField(formData, 'min_group_size');
  const maxPriceRupees = intField(formData, 'max_price_rupees');
  const slotIds = formData
    .getAll('slot_ids')
    .filter((v): v is string => typeof v === 'string' && v !== '');
  if (groupSize === null || minGroupSize === null || maxPriceRupees === null) {
    return { ok: false, message: 'Group sizes and a price ceiling are required.' };
  }
  if (minGroupSize > groupSize)
    return { ok: false, message: 'Minimum group size cannot exceed group size.' };
  if (slotIds.length === 0) return { ok: false, message: 'Pick at least one acceptable slot.' };

  const maxPricePaise = maxPriceRupees * 100;
  try {
    // Reserve first, exactly like the agent's declare flow: the pool entry is what the draw captures against.
    const mandate = await api.createMandate(groupSize * maxPricePaise);
    const result = await api.declareInterest(releaseId, {
      user_contact: viewer.email,
      mandate_id: mandate.authorizationId,
      acceptable_slot_ids: slotIds,
      group_size: groupSize,
      min_group_size: minGroupSize,
      max_price_paise: maxPricePaise,
    });
    revalidatePath('/dashboard');
    return {
      ok: true,
      message: `Declared interest (${result.declaration_id}). The draw decides allocation.`,
    };
  } catch (error) {
    return { ok: false, message: messageOf(error) };
  }
}

export async function buyAction(_prev: ActionState, formData: FormData): Promise<ActionState> {
  const viewer = await requireViewer();
  const releaseId = formData.get('release_id');
  const slotId = formData.get('slot_id');
  const quantity = intField(formData, 'quantity');
  if (
    typeof releaseId !== 'string' ||
    typeof slotId !== 'string' ||
    quantity === null ||
    quantity < 1
  ) {
    return { ok: false, message: 'Pick a slot and a quantity of at least 1.' };
  }

  try {
    const release = await api.getRelease(releaseId);
    const slot = release.slots.find(candidate => candidate.slot_id === slotId);
    if (!slot) return { ok: false, message: 'That slot is not part of this release.' };
    const mandate = await api.createMandate(quantity * slot.price_per_person_paise);
    const booking = await api.buyRelease(releaseId, {
      slot_id: slotId,
      quantity,
      mandate_id: mandate.authorizationId,
      user_contact: viewer.email,
    });
    revalidatePath('/dashboard');
    revalidatePath(`/events/${release.event_id}`);
    return { ok: true, message: `Booked. Reference ${booking.booking_ref}.` };
  } catch (error) {
    return { ok: false, message: messageOf(error) };
  }
}

export async function requestOrganiserAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  const viewer = await requireViewer();
  const name = formData.get('name');
  const contact = formData.get('contact');
  if (
    typeof name !== 'string' ||
    name.trim() === '' ||
    typeof contact !== 'string' ||
    contact.trim() === ''
  ) {
    return { ok: false, message: 'Name and contact are required.' };
  }
  try {
    await api.createOrganiser({
      name: name.trim(),
      contact: contact.trim(),
      requested_by: viewer.email,
    });
    revalidatePath('/organiser/request');
    return { ok: true, message: 'Request submitted. An admin will review it.' };
  } catch (error) {
    return { ok: false, message: messageOf(error) };
  }
}

export async function createEventAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  const viewer = await requireViewer();
  const organiserId = await myOrganiserId(viewer.email);
  if (!organiserId) return { ok: false, message: 'Only an approved organiser can create events.' };
  const name = formData.get('name');
  if (typeof name !== 'string' || name.trim() === '')
    return { ok: false, message: 'Event name is required.' };
  const status = formData.get('status') === 'published' ? 'published' : 'draft';
  try {
    await api.createEvent({ name: name.trim(), organiser_id: organiserId, status });
    revalidatePath('/organiser');
    return { ok: true, message: `Event created (${status}).` };
  } catch (error) {
    return { ok: false, message: messageOf(error) };
  }
}

export async function setEventStatusAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  const viewer = await requireViewer();
  const eventId = formData.get('event_id');
  const status = formData.get('status');
  if (typeof eventId !== 'string' || (status !== 'draft' && status !== 'published')) {
    return { ok: false, message: 'Bad event status update.' };
  }
  const organiserId = await myOrganiserId(viewer.email);
  const events = await api.listEvents();
  if (
    !organiserId ||
    events.find(event => event.event_id === eventId)?.organiser_id !== organiserId
  ) {
    return { ok: false, message: 'That event is not yours.' };
  }
  try {
    await api.patchEvent(eventId, { status });
    revalidatePath('/organiser');
    return { ok: true, message: `Event is now ${status}.` };
  } catch (error) {
    return { ok: false, message: messageOf(error) };
  }
}

export async function createReleaseAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  const viewer = await requireViewer();
  const organiserId = await myOrganiserId(viewer.email);
  if (!organiserId)
    return { ok: false, message: 'Only an approved organiser can create releases.' };

  const eventId = formData.get('event_id');
  const date = formData.get('date');
  const opensAt = formData.get('opens_at');
  const startsAt = formData.get('starts_at');
  const label = formData.get('label');
  const mode = formData.get('allocation_mode');
  const capacity = intField(formData, 'capacity');
  const priceRupees = intField(formData, 'price_rupees');
  if (
    typeof eventId !== 'string' ||
    typeof date !== 'string' ||
    typeof opensAt !== 'string' ||
    typeof startsAt !== 'string' ||
    typeof label !== 'string' ||
    label.trim() === ''
  ) {
    return {
      ok: false,
      message: 'Event, date, opening time, slot label and start time are required.',
    };
  }
  if (mode !== 'fair_draw' && mode !== 'instant_buy')
    return { ok: false, message: 'Pick an allocation mode.' };
  if (capacity === null || capacity < 1 || priceRupees === null || priceRupees < 1) {
    return { ok: false, message: 'Capacity and price must be positive.' };
  }

  const events = await api.listEvents({ organiser_id: organiserId });
  if (!events.some(event => event.event_id === eventId)) {
    return { ok: false, message: 'That event is not yours.' };
  }
  try {
    await api.createRelease({
      event_id: eventId,
      date,
      opens_at: new Date(opensAt).toISOString(),
      allocation_mode: mode,
      slots: [
        {
          label: label.trim(),
          starts_at: new Date(startsAt).toISOString(),
          capacity,
          price_per_person_paise: priceRupees * 100,
        },
      ],
    });
    revalidatePath('/organiser');
    return { ok: true, message: 'Release created.' };
  } catch (error) {
    return { ok: false, message: messageOf(error) };
  }
}

export async function approveOrganiserAction(
  _prev: ActionState,
  formData: FormData
): Promise<ActionState> {
  await requireRole('admin');
  const organiserId = formData.get('organiser_id');
  if (typeof organiserId !== 'string') return { ok: false, message: 'Missing organiser id.' };
  try {
    await api.approveOrganiser(organiserId);
    revalidatePath('/admin');
    return { ok: true, message: 'Organiser approved.' };
  } catch (error) {
    return { ok: false, message: messageOf(error) };
  }
}

export async function scenarioAction(_prev: ActionState, formData: FormData): Promise<ActionState> {
  await requireRole('admin');
  const target = formData.get('target');
  const scenario = formData.get('scenario');
  const delayS = intField(formData, 'delay_s');
  if (
    typeof target !== 'string' ||
    target.trim() === '' ||
    typeof scenario !== 'string' ||
    scenario === ''
  ) {
    return { ok: false, message: 'Target and scenario are required.' };
  }
  try {
    await api.setScenario({
      target: target.trim(),
      scenario,
      ...(delayS !== null ? { delay_s: delayS } : {}),
    });
    return { ok: true, message: `Scenario "${scenario}" armed for ${target}.` };
  } catch (error) {
    return { ok: false, message: messageOf(error) };
  }
}

export async function resetRunAction(
  _prev: ActionState,
  _formData: FormData
): Promise<ActionState> {
  await requireRole('admin');
  try {
    await api.resetRun();
    revalidatePath('/admin');
    return { ok: true, message: 'Run reset.' };
  } catch (error) {
    return { ok: false, message: messageOf(error) };
  }
}
