import { redirect } from 'next/navigation';

import { SignInButton } from '@/components/auth-buttons';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { currentViewer } from '@/lib/auth/roles';

export default async function SignInPage() {
  if (await currentViewer()) redirect('/dashboard');

  return (
    <main className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center px-4 py-16">
      <Card>
        <CardHeader>
          <CardTitle>Sign in to KIRRO</CardTitle>
          <CardDescription>
            Any Google account can browse and buy. Organiser access is requested from your
            dashboard; admin is seeded separately.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <SignInButton />
        </CardContent>
      </Card>
    </main>
  );
}
