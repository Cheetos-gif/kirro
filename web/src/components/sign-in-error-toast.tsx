'use client';

import { useEffect, useRef } from 'react';
import { toast } from 'sonner';

/**
 * Auth.js sends a failed sign-in back to the sign-in page with `?error=`. Nothing else on the page tells the
 * user what happened, so report it once as a toast.
 */
export function SignInErrorToast({ error }: { error?: string }) {
  const shown = useRef(false);

  useEffect(() => {
    if (!error || shown.current) return;
    shown.current = true;
    toast.error('Sign in did not finish. Please try again.');
  }, [error]);

  return null;
}
