"""The agent-stats sync (ADR-020): copies AgenticOrg's own accuracy/sample numbers into KIRRO.

The portal should be able to show what the agent has actually scored, not a hardcoded claim. Those
numbers live only on AgenticOrg, and the only reachable way to read them from a `developer`-role
account is the same cookie session the voice bridge already uses (`docs/agenticorg/platform-map.md`
§13). So this package logs in, reads each known agent's record, and PUTs the interesting fields into
`mock_server` for the portal to display with a "last synced" timestamp.

It is a mirror, not a source of truth: it never writes anything back to AgenticOrg, and the mock
stores whatever it is given without validating the numbers. A stale or failed sync leaves the previous
snapshot in place rather than one that looks fresh but isn't — which is why every entry carries its own
`synced_at`.
"""
