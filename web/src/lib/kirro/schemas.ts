import * as z from 'zod';

/**
 * Zod schemas for `mock_server`'s response shapes (docs/connectors.md). These are KIRRO mock contracts, not
 * vendor APIs — the portal parses responses through them so a shape change fails loudly instead of silently
 * rendering `undefined`.
 */

export const allocationModeSchema = z.enum(['fair_draw', 'instant_buy']);
export type AllocationMode = z.infer<typeof allocationModeSchema>;

export const slotSchema = z.object({
  slot_id: z.string(),
  label: z.string(),
  starts_at: z.string(),
  capacity: z.number().int().nonnegative(),
  price_per_person_paise: z.number().int().nonnegative(),
});
export type Slot = z.infer<typeof slotSchema>;

export const eventSchema = z.object({
  event_id: z.string(),
  name: z.string(),
  aliases: z.array(z.string()).default([]),
  generic_aliases: z.array(z.string()).default([]),
  fulfilment: z.string().default('digital'),
  organiser_id: z.string(),
  status: z.enum(['draft', 'published']),
});
export type KirroEvent = z.infer<typeof eventSchema>;

export const releaseSummarySchema = z.object({
  release_id: z.string(),
  event_id: z.string(),
  date: z.string(),
  opens_at: z.string(),
  allocation_mode: allocationModeSchema,
});
export type ReleaseSummary = z.infer<typeof releaseSummarySchema>;

export const releaseDetailSchema = z.object({
  release_id: z.string(),
  event_id: z.string(),
  opens_at: z.string(),
  allocation_mode: allocationModeSchema,
  /** MOCK field: whether the declare window is open right now (wall-clock, server-computed). */
  declarations_open: z.boolean(),
  /** MOCK field: when the declare window opens; absent/null on a release open from creation. */
  declare_window_starts_at: z.string().nullable().optional(),
  slots: z.array(slotSchema),
});
export type ReleaseDetail = z.infer<typeof releaseDetailSchema>;

export const organiserSchema = z.object({
  organiser_id: z.string(),
  name: z.string(),
  contact: z.string(),
  status: z.enum(['pending', 'approved']),
  requested_by: z.string().nullable().optional(),
});
export type Organiser = z.infer<typeof organiserSchema>;

export const declarationSchema = z.object({
  declaration_id: z.string(),
  status: z.string(),
  user_contact: z.string().optional(),
  mandate_id: z.string().optional(),
  acceptable_slot_ids: z.array(z.string()).default([]),
  group_size: z.number().int(),
  min_group_size: z.number().int(),
  max_price_paise: z.number().int(),
});
export type Declaration = z.infer<typeof declarationSchema>;

export const declarationWithReleaseSchema = declarationSchema.extend({ release_id: z.string() });
export type DeclarationWithRelease = z.infer<typeof declarationWithReleaseSchema>;

export const bookingSchema = z.object({
  booking_ref: z.string(),
  hold_id: z.string(),
  payment_id: z.string(),
  user_contact: z.string().optional(),
});
export type Booking = z.infer<typeof bookingSchema>;

export const paymentSchema = z.object({
  payment_id: z.string(),
  status: z.string(),
  amount: z.number().int(),
  auth: z.string(),
  refunded: z.boolean().default(false),
  user_contact: z.string().optional(),
});
export type Payment = z.infer<typeof paymentSchema>;

export const buyResultSchema = z.object({
  release_id: z.string(),
  slot_id: z.string(),
  quantity: z.number().int(),
  hold_id: z.string(),
  payment_id: z.string(),
  booking_ref: z.string(),
  status: z.string(),
  amount_paise: z.number().int(),
});
export type BuyResult = z.infer<typeof buyResultSchema>;

export const mandateSchema = z.object({
  authorizationId: z.string(),
  status: z.string(),
  amount: z.object({ value: z.number().int(), currency: z.string() }),
});
export type Mandate = z.infer<typeof mandateSchema>;

export const adminStateSchema = z.object({
  holds: z.number().int(),
  active_holds: z.number().int(),
  bookings: z.number().int(),
  mandates: z.number().int(),
  payments: z.number().int(),
  refunds: z.number().int(),
  released_mandates: z.number().int(),
  shipments: z.number().int(),
  organisers: z.number().int(),
  pending_organisers: z.number().int(),
  events: z.number().int(),
  releases: z.number().int(),
  declarations: z.number().int(),
  captured_paise: z.number().int(),
  refunded_paise: z.number().int(),
  user: z
    .object({
      user_contact: z.string(),
      declarations: z.array(declarationWithReleaseSchema),
      bookings: z.array(bookingSchema),
      payments: z.array(paymentSchema),
    })
    .optional(),
});
export type AdminState = z.infer<typeof adminStateSchema>;

export const pushSubscriptionSchema = z.object({
  endpoint: z.string(),
  expirationTime: z.number().nullable().optional(),
  keys: z.object({ p256dh: z.string(), auth: z.string() }),
});
export type PushSubscriptionJSON = z.infer<typeof pushSubscriptionSchema>;

export const userProfileSchema = z.object({
  user_contact: z.string(),
  notify_phone: z.string().optional(),
  push_subscription: pushSubscriptionSchema.optional(),
});
export type UserProfile = z.infer<typeof userProfileSchema>;

/**
 * One agent's last-known stats, mirrored from AgenticOrg by the stats-sync CronJob (ADR-020). Every
 * field is optional except the id: the mock stores whatever the sync job was able to read, so a field
 * the platform did not expose is absent rather than zero, and the UI must say "—" instead of "0%".
 */
export const agentStatSchema = z.object({
  agent_id: z.string(),
  name: z.string().optional(),
  status: z.string().optional(),
  accuracy: z.number().optional(),
  shadow_accuracy_current: z.number().optional(),
  shadow_sample_count: z.number().int().optional(),
  synced_at: z.string().optional(),
});
export type AgentStat = z.infer<typeof agentStatSchema>;
