'use client';

import { signIn, signOut } from 'next-auth/react';

import { Button } from '@/components/ui/button';

export function SignInButton({ label = 'Sign in with Google' }: { label?: string }) {
  return <Button onClick={() => signIn('google', { redirectTo: '/' })}>{label}</Button>;
}

export function SignOutButton() {
  return (
    <Button variant="outline" size="sm" onClick={() => signOut({ redirectTo: '/' })}>
      Sign out
    </Button>
  );
}
