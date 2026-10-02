import Image from 'next/image';
import Link from 'next/link';

import { SignInButton, SignOutButton } from '@/components/auth-buttons';
import { SITE_NAME } from '@/constants';
import type { Viewer } from '@/lib/auth/roles';

export function SiteHeader({ viewer }: { viewer: Viewer | null }) {
  const isOrganiser = viewer?.role === 'organiser' || viewer?.role === 'admin';

  return (
    <header className="border-b border-border/60">
      <nav className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-6 py-4">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2">
            <Image
              src="/kirro.webp"
              alt=""
              width={22}
              height={22}
              className="rounded-md"
              priority
            />
            <span className="font-heading text-sm font-medium tracking-tight text-foreground">
              {SITE_NAME}
            </span>
          </Link>
          <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">
            Listings
          </Link>
          <Link href="/talk" className="text-sm text-muted-foreground hover:text-foreground">
            Talk to KIRRO
          </Link>
          {viewer ? (
            <Link href="/dashboard" className="text-sm text-muted-foreground hover:text-foreground">
              My bookings
            </Link>
          ) : null}
          {isOrganiser ? (
            <Link href="/organiser" className="text-sm text-muted-foreground hover:text-foreground">
              My events
            </Link>
          ) : null}
          {viewer && !isOrganiser ? (
            <Link
              href="/organiser/request"
              className="text-sm text-muted-foreground hover:text-foreground"
            >
              Organise an event
            </Link>
          ) : null}
        </div>

        <div className="ml-auto flex items-center gap-3">
          {viewer ? (
            <>
              {viewer.role === 'admin' ? (
                <Link
                  href="/admin"
                  className="font-mono text-xs tracking-wide text-muted-foreground uppercase hover:text-foreground"
                >
                  Admin
                </Link>
              ) : null}
              <span className="h-4 w-px bg-border" aria-hidden />
              <span className="hidden font-mono text-xs text-muted-foreground sm:inline">
                {viewer.email}
              </span>
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
