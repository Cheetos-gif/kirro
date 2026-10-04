'use client';

import { Menu } from 'lucide-react';
import Image from 'next/image';
import Link from 'next/link';
import { useState } from 'react';

import { SignInButton, SignOutButton } from '@/components/auth-buttons';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import { SITE_NAME } from '@/constants';
import type { Viewer } from '@/lib/auth/roles';

const linkClass = 'text-sm text-muted-foreground hover:text-foreground';

function NavLinks({ viewer, onNavigate }: { viewer: Viewer | null; onNavigate?: () => void }) {
  const isOrganiser = viewer?.role === 'organiser' || viewer?.role === 'admin';

  return (
    <>
      <Link href="/" className={linkClass} onClick={onNavigate}>
        Listings
      </Link>
      <Link href="/talk" className={linkClass} onClick={onNavigate}>
        Talk to KIRRO
      </Link>
      {viewer ? (
        <Link href="/dashboard" className={linkClass} onClick={onNavigate}>
          My bookings
        </Link>
      ) : null}
      {viewer ? (
        <Link href="/settings" className={linkClass} onClick={onNavigate}>
          Settings
        </Link>
      ) : null}
      {isOrganiser ? (
        <Link href="/organiser" className={linkClass} onClick={onNavigate}>
          My events
        </Link>
      ) : null}
      {viewer && !isOrganiser ? (
        <Link href="/organiser/request" className={linkClass} onClick={onNavigate}>
          Organise an event
        </Link>
      ) : null}
      {viewer?.role === 'admin' ? (
        <Link
          href="/admin"
          className={linkClass}
          onClick={onNavigate}
        >
          Admin
        </Link>
      ) : null}
    </>
  );
}

function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2">
      <Image src="/kirro.webp" alt="" width={22} height={22} className="rounded-md" priority />
      <span className="font-heading text-sm font-medium tracking-tight text-foreground">{SITE_NAME}</span>
    </Link>
  );
}

export function SiteHeader({ viewer }: { viewer: Viewer | null }) {
  const [open, setOpen] = useState(false);

  return (
    <header className="border-b border-border/60">
      <nav className="mx-auto flex max-w-5xl items-center gap-4 px-4 py-4 sm:px-6">
        <Logo />

        {/* Desktop: every link inline, wrapping if the viewport is merely tight rather than truly small. */}
        <div className="hidden flex-1 flex-wrap items-center gap-x-6 gap-y-2 md:flex">
          <NavLinks viewer={viewer} />
        </div>
        <div className="hidden items-center gap-3 md:flex">
          {viewer ? (
            <>
              <span className="h-4 w-px bg-border" aria-hidden />
              <span className="hidden text-xs text-muted-foreground lg:inline">{viewer.email}</span>
              <SignOutButton />
            </>
          ) : (
            <SignInButton />
          )}
        </div>

        {/* Mobile/tablet: everything collapses behind one trigger, so no link ever wraps mid-word
            or gets pushed off-screen (the flat flex-wrap layout above did both at phone widths). */}
        <div className="ml-auto flex items-center gap-2 md:hidden">
          {viewer ? null : <SignInButton />}
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger
              render={
                <Button variant="outline" size="icon" aria-label="Open menu">
                  <Menu className="size-4" />
                </Button>
              }
            />
            <SheetContent side="right" className="w-72">
              <SheetHeader>
                <SheetTitle>
                  <Logo />
                </SheetTitle>
              </SheetHeader>
              <div className="flex flex-col gap-4 px-4 pb-6">
                <NavLinks viewer={viewer} onNavigate={() => setOpen(false)} />
                {viewer ? (
                  <>
                    <span className="h-px w-full bg-border" aria-hidden />
                    <span className="text-xs text-muted-foreground">{viewer.email}</span>
                    <SignOutButton />
                  </>
                ) : null}
              </div>
            </SheetContent>
          </Sheet>
        </div>
      </nav>
    </header>
  );
}
