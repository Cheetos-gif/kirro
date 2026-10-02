'use client';

import { useEffect, useRef } from 'react';
import { toast } from 'sonner';

import type { ActionState } from '@/app/actions';

/**
 * Show a server action's result as a toast, once per result. Server actions answer with `{ ok, message }`, so
 * this is the one place that decides a success toast from an error toast and keeps forms from each repeating it.
 *
 * The ref compares by identity: a fresh result object toasts again, while an unrelated re-render of the same
 * result does not.
 */
export function useActionToast(state: ActionState) {
  const shown = useRef<ActionState>(null);

  useEffect(() => {
    if (!state || state === shown.current) return;
    shown.current = state;
    if (state.ok) toast.success(state.message);
    else toast.error(state.message);
  }, [state]);
}
