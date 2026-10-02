'use client';

import Image from 'next/image';
import { signIn, signOut } from 'next-auth/react';

import { Button } from '@/components/ui/button';

export function SignInButton({ label = 'Sign in with Google' }: { label?: string }) {
  return (
    <Button onClick={() => signIn('google', { redirectTo: '/' })}>
      <Image
        src="/google.svg"
        alt=""
        width={16}
        height={16}
        className="shrink-0"
        data-icon="inline-start"
      />
      {label}
    </Button>
  );
}

export function SignOutButton() {
  return (
    <Button variant="outline" size="sm" onClick={() => signOut({ redirectTo: '/' })}>
      Sign out
    </Button>
  );
}
