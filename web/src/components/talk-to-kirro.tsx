import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { AGENTICORG_URL } from '@/constants';

export function TalkToKirro() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Book by chat instead</CardTitle>
        <CardDescription>KIRRO also works over WhatsApp and voice.</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-sm text-muted-foreground">
          KIRRO runs as a virtual employee on AgenticOrg, Pine Labs&apos; agent platform. Message it
          on WhatsApp or call it and say which slot you want, how many people are coming, and the
          most you will pay per person. It enters you in the draw for that release. When the window
          closes it replies on the same thread with the result, then holds your seats and confirms
          them if you got in.
        </p>
        <Button
          variant="outline"
          className="w-fit"
          render={<a href={AGENTICORG_URL} target="_blank" rel="noreferrer" />}
        >
          Open KIRRO on AgenticOrg
        </Button>
      </CardContent>
    </Card>
  );
}
