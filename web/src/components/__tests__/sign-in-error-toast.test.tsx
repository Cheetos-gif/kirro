import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { SignInErrorToast } from '@/components/sign-in-error-toast';
import { Toaster } from '@/components/ui/sonner';

vi.mock('next-themes', () => ({ useTheme: () => ({ theme: 'light' }) }));

describe('SignInErrorToast', () => {
  it('renders the failure through the toaster', async () => {
    render(
      <>
        <Toaster />
        <SignInErrorToast error="AccessDenied" />
      </>
    );
    expect(
      await screen.findByText('Sign in did not finish. Please try again.')
    ).toBeInTheDocument();
  });

  it('renders nothing when there is no error', () => {
    render(
      <>
        <Toaster />
        <SignInErrorToast />
      </>
    );
    expect(screen.queryByText('Sign in did not finish. Please try again.')).not.toBeInTheDocument();
  });
});
