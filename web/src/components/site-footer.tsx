import { AGENTICORG_URL, GITHUB_URL, SITE_NAME } from '@/constants';

function GithubMark() {
  return (
    <svg viewBox="0 0 24 24" className="size-3.5" fill="currentColor" aria-hidden>
      <path d="M12 .3a12 12 0 0 0-3.8 23.38c.6.1.82-.26.82-.58v-2.02c-3.34.73-4.04-1.6-4.04-1.6-.55-1.4-1.34-1.76-1.34-1.76-1.1-.75.08-.73.08-.73 1.2.09 1.84 1.24 1.84 1.24 1.08 1.84 2.83 1.3 3.52 1 .1-.78.42-1.3.77-1.6-2.67-.3-5.47-1.33-5.47-5.93 0-1.31.47-2.38 1.24-3.22-.13-.3-.54-1.52.12-3.18 0 0 1-.32 3.3 1.23a11.5 11.5 0 0 1 6 0c2.3-1.55 3.3-1.23 3.3-1.23.66 1.66.25 2.88.12 3.18.77.84 1.24 1.91 1.24 3.22 0 4.61-2.81 5.63-5.49 5.92.43.37.81 1.1.81 2.22v3.29c0 .32.21.69.82.57A12 12 0 0 0 12 .3Z" />
    </svg>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-border/60">
      <div className="mx-auto flex max-w-5xl flex-wrap items-end justify-between gap-4 px-6 py-8 text-xs text-muted-foreground">
        <div className="flex flex-col gap-1">
          <span className="font-heading text-sm font-medium text-foreground">{SITE_NAME}</span>
          <span>The Ken&apos;s Case-Build 2026.</span>
          <a
            href={AGENTICORG_URL}
            target="_blank"
            rel="noreferrer"
            className="hover:text-foreground"
          >
            Agent runs on Pine Labs AgenticOrg.
          </a>
        </div>
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1.5 hover:text-foreground"
        >
          <GithubMark />
          <span className="font-mono">Source</span>
        </a>
      </div>
    </footer>
  );
}
