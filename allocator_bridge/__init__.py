"""The allocator-trigger bridge (ADR-018): drives the "Kirro Allocator" agent on a schedule.

AgenticOrg's own "Kirro Window Allocation" Workflow executes zero steps on every run, and the
scheduler connector it would need is not grantable from a `developer`-role account
(`docs/agenticorg/platform-bugs.md` Bug 2). Driving the Allocator agent directly over its chat API
works and is already verified (`docs/testing.md`), so this package is a relay, not a decision-maker:
it only decides *when* to say "run the allocation for release X"; every allocation, hold, capture and
release decision stays the Allocator agent's own tool-calling loop, exactly as ADR-011 requires of the
voice bridge for the Declare agent.
"""
