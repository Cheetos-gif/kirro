'use client';

import { useState } from 'react';
import * as z from 'zod';

import { Button } from '@/components/ui/button';
import { Card, CardDescription, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
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
      <Card className="w-full max-w-xl p-6">
        <CardTitle className="text-xl">Is this right?</CardTitle>
        <p className="rounded-2xl bg-muted/40 p-4 text-sm leading-6">{readbackText}</p>
        <div className="flex gap-3">
          <Button onClick={() => onReadbackResponse(true)} disabled={pending}>
            Yes, go ahead
          </Button>
          <Button variant="outline" onClick={() => onReadbackResponse(false)} disabled={pending}>
            Let me redo it
          </Button>
        </div>
      </Card>
    );
  }

  if (step === 'authorised' && result) {
    const rupees = result.mandate_paise
      ? (result.mandate_paise / 100).toLocaleString('en-IN')
      : null;
    return (
      <Card className="w-full max-w-xl p-6">
        <CardTitle className="text-xl">You&apos;re in</CardTitle>
        <CardDescription>
          Status: <span className="font-medium text-foreground">{result.state}</span>
        </CardDescription>
        {rupees && (
          <CardDescription>
            Up to <span className="font-medium text-foreground">₹{rupees}</span> is held, not
            charged.
          </CardDescription>
        )}
        <p className="text-sm leading-6 text-muted-foreground">
          Nothing more to do. We&apos;ll charge you only if you get a slot, and tell you either way.
        </p>
      </Card>
    );
  }

  if (step === 'error') {
    return (
      <Card className="w-full max-w-xl gap-4 p-6">
        <p className="text-sm text-destructive">{error}</p>
        <Button variant="outline" onClick={() => setStep('intake')} className="w-fit">
          Try again
        </Button>
      </Card>
    );
  }

  return (
    <Card className="w-full max-w-xl p-6">
      <form onSubmit={form.handleSubmit(onIntake)} className="flex flex-col gap-4">
        <Field
          label="What do you want?"
          placeholder="Badminton court"
          error={form.formState.errors.event}
        >
          <Input {...form.register('event')} />
        </Field>
        <Field label="When?" placeholder="Saturday" error={form.formState.errors.date}>
          <Input {...form.register('date')} />
        </Field>
        <Field label="Group size" placeholder="4 people" error={form.formState.errors.group_size}>
          <Input {...form.register('group_size')} />
        </Field>
        <Field
          label="Max price per person"
          placeholder="₹300"
          error={form.formState.errors.max_price}
        >
          <Input {...form.register('max_price')} />
        </Field>
        <Field label="Minimum group size" placeholder="optional">
          <Input {...form.register('min_group_size')} />
        </Field>
        <Field label="Preferred time" placeholder="optional, e.g. 7-9 am">
          <Input {...form.register('time_window')} />
        </Field>
        {openFieldNote && <p className="text-sm text-destructive">{openFieldNote}</p>}
        {error && <p className="text-sm text-destructive">{error}</p>}
        <Button type="submit" disabled={pending}>
          {pending ? 'Declaring…' : 'Declare'}
        </Button>
      </form>
    </Card>
  );
}

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
    <div className="flex flex-col gap-1.5">
      <Label>{label}</Label>
      {children}
      <span className="text-xs text-muted-foreground">{placeholder}</span>
      {error?.message && <span className="text-xs text-destructive">{error.message}</span>}
    </div>
  );
}
