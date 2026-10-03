'use client';

import { useActionState } from 'react';

import {
  approveOrganiserAction,
  resetRunAction,
  scenarioAction,
  type ActionState,
} from '@/app/actions';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useActionToast } from '@/hooks/use-action-toast';

const SCENARIOS = [
  'success',
  'no_inventory',
  'insufficient_balance',
  'timeout',
  'delayed',
  'malformed',
  'duplicate',
  'booking_expired',
  'payment_failure',
  'partial_group',
  'upstream_500',
];

export function ApproveOrganiserButton({ organiserId }: { organiserId: string }) {
  const [state, action, pending] = useActionState<ActionState, FormData>(
    approveOrganiserAction,
    null
  );
  useActionToast(state);

  return (
    <form action={action} className="flex items-center gap-2">
      <input type="hidden" name="organiser_id" value={organiserId} />
      <Button type="submit" size="sm" disabled={pending}>
        {pending ? 'Approving...' : 'Approve'}
      </Button>
    </form>
  );
}

export function ScenarioForm() {
  const [state, action, pending] = useActionState<ActionState, FormData>(scenarioAction, null);
  useActionToast(state);

  return (
    <form action={action} className="flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="scenario-target">Target</Label>
          <Input
            id="scenario-target"
            name="target"
            placeholder="venue.buy or *"
            defaultValue="*"
            required
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="scenario-name">Scenario</Label>
          <Select name="scenario" defaultValue="success">
            <SelectTrigger id="scenario-name" className="w-full">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SCENARIOS.map(scenario => (
                <SelectItem key={scenario} value={scenario}>
                  {scenario}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="scenario-delay">Delay (seconds)</Label>
          <Input id="scenario-delay" name="delay_s" type="number" min={0} placeholder="optional" />
        </div>
      </div>
      <Button type="submit" disabled={pending} className="w-fit">
        {pending ? 'Setting...' : 'Set scenario'}
      </Button>
    </form>
  );
}

export function ResetRunButton() {
  const [state, action, pending] = useActionState<ActionState, FormData>(resetRunAction, null);
  useActionToast(state);

  return (
    <form action={action}>
      <Button type="submit" variant="destructive" size="sm" disabled={pending}>
        {pending ? 'Clearing...' : 'Clear this run'}
      </Button>
    </form>
  );
}
