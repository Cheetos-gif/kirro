import Link from 'next/link';

import { SignInButton, SignOutButton } from '@/components/auth-buttons';
import { Badge } from '@/components/ui/badge';
import type { Viewer } from '@/lib/auth/roles';

export function SiteHeader({ viewer }: { viewer: Viewer | null }) {
  const isOrganiser = viewer?.role === 'organiser' || viewer?.role === 'admin';

  return (
    <header className="border-b border-border/60">
      <nav className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3">
        <Link href="/" className="font-heading text-base font-semibold tracking-tight">
          KIRRO
        </Link>
        <div className="flex items-center gap-4 text-sm text-muted-foreground">
          <Link href="/" className="hover:text-foreground">
            Listings
          </Link>
          {viewer ? (
            <Link href="/dashboard" className="hover:text-foreground">
              Dashboard
            </Link>
          ) : null}
          {isOrganiser ? (
            <Link href="/organiser" className="hover:text-foreground">
              Organiser
            </Link>
          ) : null}
          {viewer && !isOrganiser ? (
            <Link href="/organiser/request" className="hover:text-foreground">
              Become an organiser
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
