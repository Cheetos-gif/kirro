import { AGENTICORG_URL } from '@/constants';

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-border/60">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-2 px-4 py-4 text-xs text-muted-foreground">
        <span>KIRRO, a demo for The Ken&apos;s Case-Build 2026.</span>
        <a href={AGENTICORG_URL} target="_blank" rel="noreferrer" className="hover:text-foreground">
          Runs on AgenticOrg
        </a>
      </div>
    </footer>
  );
}
