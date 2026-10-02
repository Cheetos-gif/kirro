import Link from 'next/link';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { requireViewer } from '@/lib/auth/roles';
import * as api from '@/lib/kirro/api';
import { formatPaise } from '@/lib/kirro/format';

export default async function DashboardPage() {
  const viewer = await requireViewer();

  let user;
  try {
    const state = await api.adminState(viewer.email);
    user = state.user;
  } catch (error) {
    return (
      <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-16">
        <Alert variant="destructive">
          <AlertTitle>Cannot reach the booking service</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : 'Something went wrong.'}
          </AlertDescription>
        </Alert>
      </main>
    );
  }

  const declarations = user?.declarations ?? [];
  const bookings = user?.bookings ?? [];
  const payments = user?.payments ?? [];

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-6 py-10">
      <header className="mb-10 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="font-heading text-2xl font-medium tracking-tight text-foreground">
            My bookings
          </h1>
          <p className="mt-1 font-mono text-xs text-muted-foreground">
            {viewer.email} &middot; {viewer.role}
          </p>
        </div>
        {viewer.role === 'user' ? (
          <Button
            variant="outline"
            size="sm"
            render={<Link href="/organiser/request" />}
            nativeButton={false}
          >
            Organise an event
          </Button>
        ) : null}
      </header>

      <section className="border-t border-border py-8">
        <h2 className="font-heading text-lg font-medium text-foreground">Draw entries</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Draw results aren&apos;t shown here yet &mdash; the agent notifies you directly when the
          window closes. This list is what you declared.
        </p>
        {declarations.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">You have not joined a draw yet.</p>
        ) : (
          <Table className="mt-4">
            <TableHeader>
              <TableRow>
                <TableHead>Release</TableHead>
                <TableHead>People</TableHead>
                <TableHead>Most you will pay</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {declarations.map(declaration => (
                <TableRow key={declaration.declaration_id}>
                  <TableCell className="font-mono text-xs">{declaration.release_id}</TableCell>
                  <TableCell>
                    {declaration.min_group_size} to {declaration.group_size}
                  </TableCell>
                  <TableCell>{formatPaise(declaration.max_price_paise)} each</TableCell>
                  <TableCell>
                    <Badge variant="secondary">Entered</Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <section className="border-t border-border py-8">
        <h2 className="font-heading text-lg font-medium text-foreground">Bookings</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Seats bought outright through this site. Only purchases made here show up.
        </p>
        {bookings.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">No bookings yet.</p>
        ) : (
          <Table className="mt-4">
            <TableHeader>
              <TableRow>
                <TableHead>Reference</TableHead>
                <TableHead>Hold</TableHead>
                <TableHead>Payment</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {bookings.map(booking => (
                <TableRow key={booking.booking_ref}>
                  <TableCell className="font-mono text-xs font-medium">
                    {booking.booking_ref}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {booking.hold_id}
                  </TableCell>
                  <TableCell className="font-mono text-xs text-muted-foreground">
                    {booking.payment_id}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>

      <section className="border-t border-border py-8">
        <h2 className="font-heading text-lg font-medium text-foreground">Payments (mock)</h2>
        <p className="mt-1 text-sm text-muted-foreground">Mock Pine Labs charges on your account.</p>
        {payments.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">No payments yet.</p>
        ) : (
          <Table className="mt-4">
            <TableHeader>
              <TableRow>
                <TableHead>Payment</TableHead>
                <TableHead>Amount</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Refunded</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {payments.map(payment => (
                <TableRow key={payment.payment_id}>
                  <TableCell className="font-mono text-xs font-medium">
                    {payment.payment_id}
                  </TableCell>
                  <TableCell>{formatPaise(payment.amount)}</TableCell>
                  <TableCell>
                    <Badge variant={payment.status === 'SUCCESS' ? 'secondary' : 'destructive'}>
                      {payment.status}
                    </Badge>
                  </TableCell>
                  <TableCell>{payment.refunded ? 'Yes' : 'No'}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>
    </main>
  );
}
