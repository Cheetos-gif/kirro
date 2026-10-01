import { Badge } from '@/components/ui/badge';
import { parseCheckName } from '@/lib/format-check';

/** Renders a check's name: plain text for builtins, a small key/value grid for the JSON ones. */
export function CheckName({ name }: { name: string }) {
  const parsed = parseCheckName(name);
  if (!parsed) return <span>{name}</span>;

  const { type, forbidden, ...rest } = parsed;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {forbidden === true && <Badge variant="destructive">forbidden</Badge>}
      {typeof type === 'string' && <Badge variant="outline">{type}</Badge>}
      {Object.entries(rest).map(([k, v]) => (
        <span key={k} className="rounded-full bg-muted px-2 py-0.5 text-xs">
          <span className="text-muted-foreground">{k}</span>
          <span className="mx-1 text-muted-foreground/50">·</span>
          <span className="font-medium">{typeof v === 'string' ? v : JSON.stringify(v)}</span>
        </span>
      ))}
    </div>
  );
}
