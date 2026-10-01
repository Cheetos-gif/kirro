'use client';

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { EvalRunSummary } from '@/lib/kirro';

import { CheckName } from './check-name';

export function EvalRunsTable({ runs }: { runs: EvalRunSummary[] }) {
  return (
    <Accordion>
      {runs.map(({ run_id, verdict }) => {
        const passedCount = verdict.checks.filter(c => c.passed).length;
        return (
          <AccordionItem key={run_id} value={run_id}>
            <AccordionTrigger>
              <div className="grid flex-1 grid-cols-2 items-center gap-3 sm:grid-cols-5">
                <span className="truncate font-mono text-xs text-muted-foreground">{run_id}</span>
                <span>{verdict.case}</span>
                <Badge variant={verdict.passed ? 'default' : 'destructive'}>
                  {verdict.passed ? 'Passed' : 'Failed'}
                </Badge>
                <span className="text-muted-foreground">{verdict.final_state}</span>
                <span className="text-muted-foreground">
                  {passedCount}/{verdict.checks.length} checks
                </span>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Check</TableHead>
                    <TableHead>Result</TableHead>
                    <TableHead>Detail</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {verdict.checks.map((c, i) => (
                    <TableRow key={i}>
                      <TableCell className="max-w-96 min-w-96 whitespace-normal">
                        <CheckName name={c.name} />
                      </TableCell>
                      <TableCell>
                        <Badge variant={c.passed ? 'default' : 'destructive'}>
                          {c.passed ? 'Pass' : 'Fail'}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-72 min-w-72 whitespace-normal text-muted-foreground">
                        {c.detail || '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </AccordionContent>
          </AccordionItem>
        );
      })}
    </Accordion>
  );
}
