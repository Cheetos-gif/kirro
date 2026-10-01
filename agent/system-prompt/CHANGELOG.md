# System prompt changelog

Rule: a version file is immutable once any eval has run against it. Change = copy to the next version, edit, add a
row here, repoint current.md. Each row names the failing eval and run that forced the change.

| version | date | triggered_by | change | expected effect |
|---|---|---|---|---|
| v0 | 2026-10-01 | initial draft from docs/architecture-plan-v1.md section 13 | first draft | baseline for E01-E10 |
