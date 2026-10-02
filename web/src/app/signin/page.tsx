import { redirect } from 'next/navigation';

import { SignInButton } from '@/components/auth-buttons';
import { SignInErrorToast } from '@/components/sign-in-error-toast';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { currentViewer } from '@/lib/auth/roles';

export default async function SignInPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;
  if (await currentViewer()) redirect('/dashboard');

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-4 py-16">
      <SignInErrorToast error={error} />
      <Card>
        <CardHeader>
          <CardTitle>Sign in</CardTitle>
          <CardDescription>
            Use your Google account. Everyone starts as a user, and you can ask to organise events
            from your bookings page once you are in.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SignInButton label="Continue with Google" />
        </CardContent>
      </Card>
    </main>
  );
}
