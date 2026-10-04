import Link from 'next/link';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { requireViewer } from '@/lib/auth/roles';
import * as api from '@/lib/kirro/api';

import { PhoneSettingsForm } from './phone-form';
import { PushNotificationsForm } from './push-form';

export default async function SettingsPage() {
  const viewer = await requireViewer();

  let notifyPhone: string | undefined;
  try {
    notifyPhone = (await api.getUserProfile(viewer.email)).notify_phone;
  } catch (error) {
    return (
      <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-16">
        <Alert variant="destructive">
          <AlertTitle>Cannot reach the booking service</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : 'Something went wrong.'}
          </AlertDescription>
        </Alert>
      </main>
    );
  }

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 px-6 py-10">
      <header className="mb-10">
        <h1 className="font-heading text-2xl font-medium tracking-tight text-foreground">
          Settings
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Where KIRRO reaches you about a draw.
        </p>
      </header>

      <section className="border-t border-border py-8">
        <h2 className="font-heading text-lg font-medium text-foreground">Result notifications</h2>
        <p className="mt-1 mb-4 max-w-prose text-sm text-muted-foreground">
          The draw result is delivered on WhatsApp, so a number is required before you can enter one.
          WhatsApp also only lets a business message you inside a 24-hour window you open by
          messaging it first &mdash; the{' '}
          <Link href="/talk" className="text-foreground underline underline-offset-4">
            Talk to KIRRO
          </Link>{' '}
          page offers that first message once a reservation is in.
        </p>
        <PhoneSettingsForm defaultPhone={notifyPhone} />
      </section>

      <section className="border-t border-border py-8">
        <h2 className="font-heading text-lg font-medium text-foreground">Browser notifications</h2>
        <p className="mt-1 mb-4 max-w-prose text-sm text-muted-foreground">
          Get a notification on this device when an instant-buy booking confirms &mdash; on top of,
          not instead of, the WhatsApp result above.
        </p>
        <PushNotificationsForm />
      </section>

      <section className="border-t border-border py-8">
        <h2 className="font-heading text-lg font-medium text-foreground">Account</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Signed in as <span className="text-foreground">{viewer.email}</span>.
        </p>
        <Button className="mt-4 w-fit" variant="outline" render={<Link href="/dashboard" />} nativeButton={false}>
          My bookings
        </Button>
      </section>
    </main>
  );
}
