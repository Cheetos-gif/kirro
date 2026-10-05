"""The WhatsApp bridge: a real-time webhook relay for Kirro's Business number (ADR-022).

A user who taps "Open WhatsApp" in the `/talk` popup sends one fixed opener message to open the
24-hour delivery window the WhatsApp Business Platform requires. This service receives that
message over Meta's Cloud API webhook and replies with a canned acknowledgement directly — never
through the AgenticOrg agent, which has no WhatsApp channel today and would otherwise price every
such turn into its scored confidence average (ADR-022).

This service holds no state and makes no booking decisions — it is a relay, same shape as
`voice_bridge/` and `allocator_bridge/`.
"""
