'use client';

import { useState } from 'react';
import * as z from 'zod';

import { Button } from '@/components/ui/button';
import { useZodForm } from '@/hooks/use-zod-form';
import type { DeclarationFull } from '@/lib/kirro';

import {
  doAuthorise,
  requestReadback,
  respondReadback,
  startDeclaration,
  submitFields,
} from './actions';

const declareSchema = z.object({
  event: z.string().min(2, 'Tell us what you want to book'),
  date: z.string().min(2, 'Give a date or day'),
  group_size: z.string().min(1, 'How many people'),
  max_price: z.string().min(1, 'Max price per person'),
  min_group_size: z.string().optional(),
  time_window: z.string().optional(),
});
type DeclareValues = z.infer<typeof declareSchema>;

type Step = 'intake' | 'readback' | 'authorised' | 'error';

export function DeclareWizard() {
  const [step, setStep] = useState<Step>('intake');
  const [did, setDid] = useState<string | null>(null);
  const [openFieldNote, setOpenFieldNote] = useState<string | null>(null);
  const [readbackText, setReadbackText] = useState<string | null>(null);
  const [result, setResult] = useState<DeclarationFull | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const form = useZodForm(declareSchema);

  async function onIntake(values: DeclareValues) {
    setPending(true);
    setError(null);
    try {
      const created = await startDeclaration();
      const state = await submitFields(created.declaration_id, values);
      setDid(created.declaration_id);
      if (state.open_field) {
        // A required field was ambiguous/invalid — code refused to guess, same as the voice flow.
        setOpenFieldNote(state.open_field_note ?? `Still need: ${state.open_field}`);
        return;
      }
      const rb = await requestReadback(created.declaration_id);
      setReadbackText(rb.text);
      setStep('readback');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
      setStep('error');
    } finally {
      setPending(false);
    }
  }

  async function onReadbackResponse(confirmed: boolean) {
    if (!did) return;
    setPending(true);
    setError(null);
    try {
      await respondReadback(did, confirmed);
      if (!confirmed) {
        setStep('intake');
        setReadbackText(null);
        return;
      }
      const full = await doAuthorise(did);
      setResult(full);
      setStep('authorised');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Something went wrong');
      setStep('error');
    } finally {
      setPending(false);
    }
  }

  if (step === 'readback') {
    return (
      <div className="flex max-w-lg flex-col gap-4">
        <h2 className="text-xl font-semibold">Here is what I understood</h2>
        <p className="rounded-lg border border-border bg-muted/40 p-4 text-sm leading-6">
          {readbackText}
        </p>
        <div className="flex gap-3">
          <Button onClick={() => onReadbackResponse(true)} disabled={pending}>
            Yes, that is right
          </Button>
          <Button variant="outline" onClick={() => onReadbackResponse(false)} disabled={pending}>
            No, let me redo it
          </Button>
        </div>
      </div>
    );
  }

  if (step === 'authorised' && result) {
    const rupees = result.mandate_paise
      ? (result.mandate_paise / 100).toLocaleString('en-IN')
      : null;
    return (
      <div className="flex max-w-lg flex-col gap-3">
        <h2 className="text-xl font-semibold">Declared and authorised</h2>
        <p className="text-sm text-muted-foreground">
          State: <span className="font-medium text-foreground">{result.state}</span>
        </p>
        {rupees && (
          <p className="text-sm text-muted-foreground">
            Blocked, not charged: <span className="font-medium text-foreground">₹{rupees}</span>
          </p>
        )}
        <p className="text-sm leading-6 text-muted-foreground">
          Nothing more to do. KIRRO waits for the booking window to open, allocates by a seeded fair
          draw, then charges and confirms — or releases the hold and tells you honestly. No
          refreshing needed.
        </p>
      </div>
    );
  }

  if (step === 'error') {
    return (
      <div className="flex max-w-lg flex-col gap-3">
        <p className="text-sm text-destructive">{error}</p>
        <Button variant="outline" onClick={() => setStep('intake')}>
          Try again
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={form.handleSubmit(onIntake)} className="flex max-w-lg flex-col gap-4">
      <Field
        label="What do you want to book?"
        placeholder="Badminton court"
        error={form.formState.errors.event}
      >
        <input className={inputClass} {...form.register('event')} />
      </Field>
      <Field label="When?" placeholder="Saturday" error={form.formState.errors.date}>
        <input className={inputClass} {...form.register('date')} />
      </Field>
      <Field label="Group size" placeholder="4 people" error={form.formState.errors.group_size}>
        <input className={inputClass} {...form.register('group_size')} />
      </Field>
      <Field label="Max price per person" placeholder="300" error={form.formState.errors.max_price}>
        <input className={inputClass} {...form.register('max_price')} />
      </Field>
      <Field label="Minimum acceptable group size (optional)" placeholder="2 people">
        <input className={inputClass} {...form.register('min_group_size')} />
      </Field>
      <Field label="Preferred time window (optional)" placeholder="7-9 am">
        <input className={inputClass} {...form.register('time_window')} />
      </Field>
      {openFieldNote && <p className="text-sm text-destructive">{openFieldNote}</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}
      <Button type="submit" disabled={pending}>
        {pending ? 'Declaring…' : 'Declare'}
      </Button>
    </form>
  );
}

const inputClass =
  'h-10 rounded-lg border border-border bg-background px-3 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/30';

function Field({
  label,
  placeholder,
  error,
  children,
}: {
  label: string;
  placeholder: string;
  error?: { message?: string };
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="text-sm font-medium">{label}</span>
      {children}
      <span className="text-xs text-muted-foreground">e.g. {placeholder}</span>
      {error?.message && <span className="text-xs text-destructive">{error.message}</span>}
    </label>
  );
}
