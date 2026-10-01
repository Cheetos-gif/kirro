import type { Metadata } from 'next';
import Image from 'next/image';

import { signIn } from '@/auth';
import { Button } from '@/components/ui/button';

export const metadata: Metadata = {
  title: 'Sign in — KIRRO',
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ callbackUrl?: string }>;
}) {
  const { callbackUrl } = await searchParams;

  return (
    <main className="flex flex-1 flex-col items-center justify-center px-6 py-24">
      <div className="flex w-full max-w-sm flex-col items-center gap-6 text-center">
        <Image src="/kirro.png" alt="KIRRO" width={48} height={48} className="rounded-xl" />
        <div className="flex flex-col gap-1.5">
          <h1 className="text-xl font-semibold tracking-tight">Sign in</h1>
          <p className="text-sm text-muted-foreground">
            Dashboard access for KIRRO — declarations, decision log, eval runs.
          </p>
        </div>
        <form
          action={async () => {
            'use server';
            await signIn('google', { redirectTo: callbackUrl ?? '/dashboard' });
          }}
          className="w-full"
        >
          <Button type="submit" className="w-full">
            Continue with Google
          </Button>
        </form>
      </div>
    </main>
  );
}
