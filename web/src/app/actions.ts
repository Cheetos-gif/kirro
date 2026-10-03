'use server';

import { revalidatePath } from 'next/cache';
import { redirect } from 'next/navigation';

import { isApiError } from '@/api';
import { requireRole, requireViewer } from '@/lib/auth/roles';
import * as api from '@/lib/kirro/api';
import type { PushSubscriptionJSON } from '@/lib/kirro/schemas';
import { sendPushNotification } from '@/lib/push/send';

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

/**
 * The mock stores a declaration's number as E.164 and refuses anything else, so the form applies the
 * same rule and reports it here rather than letting the submit fail one hop away.
 */
function normalisePhone(raw: string): string | null {
  const cleaned = raw.trim().replace(/[\s\-().]/g, '');
  const withPlus = cleaned.startsWith('00') ? `+${cleaned.slice(2)}` : cleaned;
  const digits = withPlus.startsWith('+') ? withPlus.slice(1) : '';
  return /^\d{7,15}$/.test(digits) ? withPlus : null;
}

/** The number saved in settings, or `null` when the user has not set one yet. */
async function storedNotifyPhone(email: string): Promise<string | null> {
  try {
    const profile = await api.getUserProfile(email);
    return profile.notify_phone ?? null;
  } catch {
    // An unreachable profile must read as "not set yet", not as a failed declaration: the message
    // then points at settings, which is where the fix is.
    return null;
  }
}

export async function savePhoneAction(_prev: ActionState, formData: FormData): Promise<ActionState> {
  const viewer = await requireViewer();
  const raw = formData.get('notify_phone');
  const notifyPhone = typeof raw === 'string' ? normalisePhone(raw) : null;
  if (notifyPhone === null) {
    return { ok: false, message: 'Enter a number with its country code, e.g. +919876543210.' };
  }
  try {
    await api.setUserProfile(viewer.email, { notify_phone: notifyPhone });
    revalidatePath('/settings');
    return { ok: true, message: `Saved. Draw results go to ${notifyPhone} on WhatsApp.` };
  } catch (error) {
    return { ok: false, message: messageOf(error) };
  }
}

/** Called from the client right after `pushManager.subscribe()` succeeds, with the browser's own
 * `PushSubscription.toJSON()` output. */
export async function savePushSubscriptionAction(subscription: PushSubscriptionJSON): Promise<ActionState> {
  const viewer = await requireViewer();
  try {
    await api.setUserProfile(viewer.email, { push_subscription: subscription });
    revalidatePath('/settings');
    return { ok: true, message: 'Push notifications are on for this device.' };
  } catch (error) {
    return { ok: false, message: messageOf(error) };
  }
}

/** Called after the client's own `subscription.unsubscribe()` succeeds, so the server stops
 * holding a reference the browser itself already revoked. */
export async function clearPushSubscriptionAction(): Promise<ActionState> {
  const viewer = await requireViewer();
  try {
    await api.setUserProfile(viewer.email, { push_subscription: null });
    revalidatePath('/settings');
    return { ok: true, message: 'Push notifications are off for this device.' };
  } catch (error) {
    return { ok: false, message: messageOf(error) };
  }
}

export async function sendTestPushAction(): Promise<ActionState> {
  const viewer = await requireViewer();
  await sendPushNotification(viewer.email, {
    title: 'KIRRO test notification',
    body: 'If you can see this, push is working on this device.',
    url: '/settings',
  });
  return { ok: true, message: 'Sent. It may take a few seconds to arrive.' };
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

/**
 * The listings the quick-demo button seeds from, one chosen at random per click, so two demos don't
 * show the same slot. `aliases`/`generic_aliases` matter as much as the name: the voice agent (and
 * the talk page's own "mentioned in this call" strip) resolve free speech like "badminton" against
 * them, not against the title.
 */
const DEMO_TEMPLATES = [
  {
    name: 'Society Badminton Court',
    aliases: ['badminton'],
    generic_aliases: ['shuttle', 'court'],
    label: 'Court 1, 19:00',
    capacity: 8,
    pricePaise: 25000,
  },
  {
    name: 'Tennis Court (Club)',
    aliases: ['tennis'],
    generic_aliases: ['court', 'racket'],
    label: 'Court A, 07:00',
    capacity: 4,
    pricePaise: 60000,
  },
  {
    name: 'Opening Night Movie',
    aliases: ['movie'],
    generic_aliases: ['film', 'cinema', 'screening'],
    label: 'Screen 2, 21:30',
    capacity: 24,
    pricePaise: 30000,
  },
  {
    name: 'F1 Paddock Pass',
    aliases: ['f1', 'formula 1'],
    generic_aliases: ['paddock', 'race'],
    label: 'Paddock, 14:00',
    capacity: 6,
    pricePaise: 900000,
  },
  {
    name: 'Rooftop Yoga Session',
    aliases: ['yoga'],
    generic_aliases: ['rooftop', 'class'],
    label: 'Rooftop, 06:30',
    capacity: 12,
    pricePaise: 20000,
  },
  {
    name: 'Pottery Workshop',
    aliases: ['pottery', 'ceramics'],
    generic_aliases: ['workshop', 'clay'],
    label: 'Bench 3, 11:00',
    capacity: 5,
    pricePaise: 150000,
  },
];

/**
 * The seeded release's declare window: it opens three minutes after the click, and stays open for
 * three minutes after that. Both numbers are deliberate — the wait is a short, predictable beat for
 * the presenter to set the scene (and is counted down on `/talk`), and the window is only as long as
 * a demo needs, so the allocator-trigger CronJob's own 5-minute schedule draws the release soon after
 * instead of the caller waiting out a long sale.
 */
const QUICK_DEMO_OPENS_AFTER_MS = 3 * 60_000;
const QUICK_DEMO_WINDOW_MS = 3 * 60_000;

/**
 * Seed one ready-to-declare fair-draw release, immediately open, so a demo can start on the voice
 * agent instead of on event setup (#32). Organiser/admin only, exactly like `createReleaseAction` —
 * it writes real inventory, so it is not open to an anonymous click.
 *
 * On success it redirects to `/talk?demo=<event_id>`: the intended way to use the seeded event is to
 * say it out loud to the agent, not to fill in the declare form.
 */
export async function createQuickDemoAction(_prev: ActionState, _formData: FormData): Promise<ActionState> {
  const viewer = await requireViewer();
  const organiserId = await myOrganiserId(viewer.email);
  if (!organiserId) {
    return { ok: false, message: 'Only an approved organiser can seed a demo event.' };
  }

  let eventId: string;
  try {
    const events = await api.listEvents();
    const template = DEMO_TEMPLATES[Math.floor(Math.random() * DEMO_TEMPLATES.length)];
    // Two demos of the same kind would be ambiguous to speak ("the pottery one" — which one?), so a
    // repeated title gets a short tag. The common case is the plain name.
    const taken = new Set(events.filter(event => event.status === 'published').map(event => event.name));
    const name = taken.has(template.name)
      ? `${template.name} ${Math.random().toString(36).slice(2, 4).toUpperCase()}`
      : template.name;

    const created = await api.createEvent({
      name,
      organiser_id: organiserId,
      status: 'published',
      aliases: template.aliases,
      generic_aliases: template.generic_aliases,
    });
    eventId = created.event_id;

    const now = Date.now();
    const opensAt = new Date(now + QUICK_DEMO_OPENS_AFTER_MS + QUICK_DEMO_WINDOW_MS).toISOString();
    await api.createRelease({
      event_id: eventId,
      date: new Date(now).toISOString().slice(0, 10),
      declare_window_starts_at: new Date(now + QUICK_DEMO_OPENS_AFTER_MS).toISOString(),
      opens_at: opensAt,
      allocation_mode: 'fair_draw',
      slots: [
        {
          label: template.label,
          starts_at: opensAt,
          capacity: template.capacity,
          price_per_person_paise: template.pricePaise,
        },
      ],
    });
  } catch (error) {
    return { ok: false, message: messageOf(error) };
  }

  revalidatePath(`/events/${eventId}`);
  revalidatePath('/talk');
  // Straight to the voice channel: the seeded event exists to be spoken about to the agent.
  redirect(`/talk?demo=${eventId}`);
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

  // The number is an account attribute, not a form field: the mock resolves it from what the user saved
  // in settings, under this contact. Refuse here only so the failure reads as an instruction rather than
  // a bare API error.
  if ((await storedNotifyPhone(viewer.email)) === null) {
    return {
      ok: false,
      message: 'Add a WhatsApp number with its country code in settings before entering the draw.',
    };
  }

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
      message: `Entered. Reference ${result.declaration_id}. The draw runs when the window closes.`,
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
    // Best-effort: a push failure must never undo or mask a real booking (sendPushNotification
    // already swallows its own errors internally).
    void sendPushNotification(viewer.email, {
      title: 'Booking confirmed',
      body: `${release.event_id} — reference ${booking.booking_ref}.`,
      url: '/dashboard',
    });
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
    return { ok: true, message: 'Request sent. The team will review it.' };
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
    return {
      ok: true,
      message:
        status === 'published' ? 'Event created and published.' : 'Event created as a draft.',
    };
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
    return { ok: true, message: 'Approved.' };
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
    return { ok: true, message: `Scenario set: ${scenario} on ${target}.` };
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
    return { ok: true, message: 'Run cleared.' };
  } catch (error) {
    return { ok: false, message: messageOf(error) };
  }
}
