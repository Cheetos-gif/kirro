# ADR-009: Assumptions made without asking

Status: accepted (2026-10-01)

- No competition materials existed locally; the Opus plan is the only design input.
- Default group minimum equals group size (all or none) and is stated in the read-back.
- 'Any day' / flexible dates are not accepted as a date in v0; the agent asks for a date.
- Time windows need am/pm so they never collide with price ranges ('8 to 10k').
- Allocation history (allocations_last_30d) comes from fixtures; real source unknown.
- Pine Labs mock collapses challenge/token/capture into one execute call; real flow documented in docs/connectors.md.
- Only prompt v0 exists; a v1 will be created from a real failing live eval, not invented.
