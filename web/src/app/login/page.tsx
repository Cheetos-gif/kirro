import type { Metadata } from 'next';
import Image from 'next/image';
import { FcGoogle } from 'react-icons/fc';

import { signIn } from '@/auth';
import { Button } from '@/components/ui/button';
import { Card, CardDescription, CardTitle } from '@/components/ui/card';

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
      <Card className="w-full max-w-sm items-center gap-6 p-8 text-center">
        <Image src="/kirro.png" alt="KIRRO" width={48} height={48} className="rounded-xl" />
        <div className="flex flex-col gap-1.5">
          <CardTitle className="text-xl">Sign in</CardTitle>
          <CardDescription>View declarations and the decision log.</CardDescription>
        </div>
        <form
          action={async () => {
            'use server';
            await signIn('google', { redirectTo: callbackUrl ?? '/dashboard' });
          }}
          className="w-full"
        >
          <Button type="submit" variant="outline" className="w-full">
            <FcGoogle className="size-4" />
            Continue with Google
          </Button>
        </form>
      </Card>
    </main>
  );
}
