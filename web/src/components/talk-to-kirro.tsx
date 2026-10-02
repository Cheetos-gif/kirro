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
          sequence described above. We&apos;ve tested it live through AgenticOrg&apos;s chat panel;
          see <code className="font-mono">docs/testing.md</code> for the run log.
        </p>
        <Button
          variant="outline"
          className="w-fit"
          render={<a href={AGENTICORG_URL} target="_blank" rel="noreferrer" />}
          nativeButton={false}
        >
          Open KIRRO on AgenticOrg
        </Button>
      </CardContent>
    </Card>
  );
}
