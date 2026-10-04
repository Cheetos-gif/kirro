import Link from 'next/link';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { AGENTICORG_URL } from '@/constants';

export function TalkToKirro() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Prefer to just say it?</CardTitle>
        <CardDescription>
          Call KIRRO and ask for a slot out loud, instead of filling in a form.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">
          Tell it what you want: the event, your group size, and the most you are willing to pay.
          If the slot&apos;s popular, it puts you in the same fair pick as the form above, then
          lets you know what happened. You talk in your browser and it talks back, no typing
          required.
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <Button className="w-fit" render={<Link href="/talk" />} nativeButton={false}>
            Talk to KIRRO
          </Button>
          <Button
            variant="outline"
            className="w-fit"
            render={<a href={AGENTICORG_URL} target="_blank" rel="noreferrer" />}
            nativeButton={false}
          >
            Open on AgenticOrg
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
