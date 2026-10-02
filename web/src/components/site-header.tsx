import Image from 'next/image';
import Link from 'next/link';

import { SignInButton, SignOutButton } from '@/components/auth-buttons';
import { Badge } from '@/components/ui/badge';
import { SITE_NAME } from '@/constants';
import type { Viewer } from '@/lib/auth/roles';

export function SiteHeader({ viewer }: { viewer: Viewer | null }) {
  const isOrganiser = viewer?.role === 'organiser' || viewer?.role === 'admin';

  return (
    <header className="border-b border-border/60">
      <nav className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <Link href="/" className="flex items-center gap-2">
          <Image src="/kirro.webp" alt="" width={26} height={26} className="rounded-md" priority />
          <span className="font-heading text-base font-semibold tracking-tight">{SITE_NAME}</span>
        </Link>
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <Link href="/" className="hover:text-foreground">
            Listings
          </Link>
          {viewer ? (
            <Link href="/dashboard" className="hover:text-foreground">
              My bookings
            </Link>
          ) : null}
          {isOrganiser ? (
            <Link href="/organiser" className="hover:text-foreground">
              My events
            </Link>
          ) : null}
          {viewer && !isOrganiser ? (
            <Link href="/organiser/request" className="hover:text-foreground">
              Organise an event
            </Link>
          ) : null}
          {viewer?.role === 'admin' ? (
            <Link href="/admin" className="hover:text-foreground">
              Admin
            </Link>
          ) : null}
        </div>
        <div className="ml-auto flex items-center gap-2">
          {viewer ? (
            <>
              <Badge variant="secondary">{viewer.role}</Badge>
              <span className="hidden text-xs text-muted-foreground sm:inline">{viewer.email}</span>
              <SignOutButton />
            </>
          ) : (
            <SignInButton />
          )}
        </div>
      </nav>
    </header>
  );
}
