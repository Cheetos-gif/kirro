import Link from 'next/link';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
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
      <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-16">
        <Alert variant="destructive">
          <AlertTitle>Could not load your dashboard</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : 'Mock server unreachable.'}
          </AlertDescription>
        </Alert>
      </main>
    );
  }

  const declarations = user?.declarations ?? [];
  const bookings = user?.bookings ?? [];
  const payments = user?.payments ?? [];

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-10">
      <header className="mb-6 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="font-heading text-2xl font-semibold tracking-tight">Your dashboard</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {viewer.email} · role {viewer.role}
          </p>
        </div>
        {viewer.role === 'user' ? (
          <Button variant="outline" size="sm" render={<Link href="/organiser/request" />}>
            Request organiser access
          </Button>
        ) : null}
      </header>

      <div className="flex flex-col gap-6">
        <Card>
          <CardHeader>
            <CardTitle>Declared interest</CardTitle>
            <CardDescription>
              Entries in a release&apos;s pool. Allocation is decided by the fair draw, not by order
              of arrival.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {declarations.length === 0 ? (
              <p className="text-sm text-muted-foreground">No declarations yet.</p>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Release</TableHead>
                    <TableHead>Group</TableHead>
                    <TableHead>Ceiling</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {declarations.map(declaration => (
                    <TableRow key={declaration.declaration_id}>
                      <TableCell>{declaration.release_id}</TableCell>
                      <TableCell>
                        {declaration.min_group_size}–{declaration.group_size}
                      </TableCell>
                      <TableCell>{formatPaise(declaration.max_price_paise)}</TableCell>
                      <TableCell>
                        <Badge variant="secondary">{declaration.status}</Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Bookings</CardTitle>
            <CardDescription>
              Confirmed instant buys. Fair-draw confirmations appear once the draw runs.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {bookings.length === 0 ? (
              <p className="text-sm text-muted-foreground">No bookings yet.</p>
            ) : (
              <Table>
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
                      <TableCell className="font-medium">{booking.booking_ref}</TableCell>
                      <TableCell className="text-muted-foreground">{booking.hold_id}</TableCell>
                      <TableCell className="text-muted-foreground">{booking.payment_id}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Payments</CardTitle>
            <CardDescription>Captured against your mandates.</CardDescription>
          </CardHeader>
          <CardContent>
            {payments.length === 0 ? (
              <p className="text-sm text-muted-foreground">No payments yet.</p>
            ) : (
              <Table>
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
                      <TableCell className="font-medium">{payment.payment_id}</TableCell>
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
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
