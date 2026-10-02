import Link from 'next/link';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { requireViewer } from '@/lib/auth/roles';
import * as api from '@/lib/kirro/api';

import { RequestOrganiserForm } from './request-form';

export default async function OrganiserRequestPage() {
  const viewer = await requireViewer();

  const mine = (await api.listOrganisers()).filter(
    organiser => organiser.requested_by?.toLowerCase() === viewer.email.toLowerCase()
  );
  const approved = mine.find(organiser => organiser.status === 'approved');
  const pending = mine.find(organiser => organiser.status === 'pending');

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 px-4 py-10">
      <h1 className="mb-6 font-heading text-2xl font-semibold tracking-tight">Organise an event</h1>

      {approved ? (
        <Alert>
          <AlertTitle>
            You are set up as <Badge variant="secondary">{approved.name}</Badge>
          </AlertTitle>
          <AlertDescription className="flex flex-col gap-3">
            <span>You can create events and releases from here.</span>
            <Button size="sm" className="w-fit" render={<Link href="/organiser" />}>
              Go to my events
            </Button>
          </AlertDescription>
        </Alert>
      ) : pending ? (
        <Alert>
          <AlertTitle>Your request is with the team</AlertTitle>
          <AlertDescription>
            You will keep booking like any other user until it is approved.
          </AlertDescription>
        </Alert>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Ask to organise</CardTitle>
            <CardDescription>
              Organisers put events and releases on the site. The team approves requests, and you
              can book like anyone else while you wait.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <RequestOrganiserForm defaultName={viewer.name ?? undefined} />
          </CardContent>
        </Card>
      )}
    </main>
  );
}
