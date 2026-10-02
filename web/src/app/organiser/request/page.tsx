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
      <h1 className="mb-6 font-heading text-2xl font-semibold tracking-tight">
        Become an organiser
      </h1>

      {approved ? (
        <Alert>
          <AlertTitle>
            Approved <Badge variant="secondary">{approved.name}</Badge>
          </AlertTitle>
          <AlertDescription className="flex flex-col gap-3">
            <span>Your organiser account is active.</span>
            <Button size="sm" className="w-fit" render={<Link href="/organiser" />}>
              Go to organiser dashboard
            </Button>
          </AlertDescription>
        </Alert>
      ) : pending ? (
        <Alert>
          <AlertTitle>Request under review</AlertTitle>
          <AlertDescription>
            An admin will approve or decline your request. You are a normal user until then.
          </AlertDescription>
        </Alert>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Request organiser access</CardTitle>
            <CardDescription>
              Organisers create events and releases. Requests are approved by an admin; you stay a
              normal user until then.
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
