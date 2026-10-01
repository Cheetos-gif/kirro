import Image from 'next/image';
import Link from 'next/link';

export function NavHeader() {
  return (
    <header className="border-b border-border">
      <nav className="mx-auto flex w-full max-w-4xl items-center justify-between px-6 py-4 text-sm">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
          <Image src="/kirro.png" alt="KIRRO" width={24} height={24} className="rounded-md" />
          KIRRO
        </Link>
        <div className="flex gap-6 text-muted-foreground">
          <Link href="/declare" className="hover:text-foreground">
            Declare
          </Link>
          <Link href="/dashboard" className="hover:text-foreground">
            Dashboard
          </Link>
        </div>
      </nav>
    </header>
  );
}
