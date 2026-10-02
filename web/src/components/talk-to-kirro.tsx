import Link from 'next/link';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { AGENTICORG_URL } from '@/constants';

export function TalkToKirro() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>The agent, not the form</CardTitle>
        <CardDescription>
          KIRRO runs as a virtual employee on AgenticOrg, Pine Labs&apos; agent platform.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">
          This site is one way to declare interest. The agent is the other: tell it a slot, your
          group size, and your price ceiling, and it does the same declare &rarr; draw &rarr; book
          sequence described above. Talk to it in the browser &mdash; Gnani transcribes you and
          speaks the reply back.
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
