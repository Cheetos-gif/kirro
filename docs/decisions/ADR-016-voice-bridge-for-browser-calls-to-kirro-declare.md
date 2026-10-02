# ADR-016: A voice bridge so a user can talk to Kirro Declare from the browser, Gnani doing STT/TTS

Status: **amended by ADR-017** (2026-10-02) — the browser channel, its purpose, and the Gnani-vs-phone
reasoning below all stand, but the hand-rolled relay and worklet described here were replaced by
LiveKit and Gnani's own LiveKit plugin. Read ADR-017 for the current mechanism; this record is kept
for the constraints it established (session-cookie auth, the shared chat thread, one call at a time).
Supersedes the phone-call plan floated earlier the same day (Twilio + a call-handling bridge) —
dropped because it costs money per call and per number
(`docs/agenticorg/platform-bugs.md` Bug 3's "what's needed" section is updated accordingly).

## Context

The brief requires a user be able to talk to the agent, not just type to it. Two platform-native options were
checked and both are closed:

- **AgenticOrg's own voice platform** (`/dashboard/voice`, `/api/v1/voice-platform/*`) exists, but publishing a
  phone endpoint needs `agenticorg:admin` (`403 Missing scope: agenticorg:admin` on `endpoints` and
  `release-approvals`), which this account does not have and cannot get. Its speech providers are `openai` and
  `gemini` only — no Gnani, even with admin.
- **A real phone number via Twilio** works technically (`twilio_kirro` connector is registered and healthy,
  `docs/agenticorg/platform-map.md` "Twilio — registered and healthy"), but costs real money per call-minute and
  requires buying a number; the user declined this specifically to avoid that cost.

What remains free and fully reachable from a `developer`-role account: Gnani's STT/TTS APIs directly
(`api.vachana.ai`, key already registered as `mcp_vachana_kirro` and live-verified, see `docs/connectors.md`), and
this repo's own `web/` portal, which already exists, is deployed, and is the one surface KIRRO fully controls.

## Decision

Build a browser-based voice channel: a "Talk to Kirro" page in `web/` that captures the user's microphone, and a new
small, stateless **voice bridge** service that relays that audio to Gnani for STT, drives the "Kirro Declare" agent
with the resulting text, and relays the agent's text back through Gnani TTS to the browser.

```text
Browser mic (getUserMedia, 48kHz)
  -> AudioWorklet resamples to 16kHz PCM, 1024-byte frames
  -> wss://voice-kirro.<cluster-domain>/call  (new voice-bridge service)
       -> wss://api.vachana.ai/stt/v3/stream   (Gnani Prisma STT, realtime)
       -> POST https://agenticorg.hackathon.pinelabs.com/api/v1/chat/query  (Kirro Declare)
       -> wss://api.vachana.ai/api/v1/tts      (Gnani Timbre TTS, realtime)
  <- audio chunks streamed back
  <- browser <audio> plays them
```

### Why not LiveKit or Pipecat (both checked, per the user's request)

Gnani ships a plugin for each (`livekit-plugins-gnani`, `pipecat-gnani`), both Python, both thin adapters over the
same two Gnani WebSocket APIs the bridge talks to directly. Neither is adopted:

- **LiveKit** needs a LiveKit *room server* (SFU) as the WebRTC transport between the browser and the agent process
  — a third piece of infrastructure beyond the bridge and Gnani, with its own deployment, scaling, and credentials.
  Justified for multi-party or production-scale voice; this is one browser tab talking to one agent.
- **Pipecat** needs one of its own transports (WebRTC via its `SmallWebRTCTransport`/Daily, or a websocket
  transport) plus a `Pipeline`/`PipelineTask` runtime per call. It is a general voice-agent framework; here the
  only two services in the pipeline are Gnani STT and Gnani TTS — AgenticOrg's own chat API stands in for Pipecat's
  LLM stage, which the framework is not designed around (it expects to own the LLM turn, not proxy to an external
  chat endpoint it cannot see token-by-token).

Both would add a second runtime (Python, when the rest of the real-time surface the user interacts with is
Next.js/TypeScript) and a heavier operational footprint for a single-call, two-API use case. A direct WebSocket
relay using Gnani's documented realtime STT and TTS APIs (`docs.gnani.ai/api/STT/stt-websocket`,
`docs.gnani.ai/api/TTS/tts-websocket`) is the smaller, more maintainable choice and is revisited if KIRRO ever needs
multi-party calls or a general agent-voice framework.

### Why the bridge is not inside `web/` (Vercel) or inside `mock_server`

- **Not in `web/`.** `web/` is deployed to Vercel (ADR-015); Vercel's serverless functions are request/response with
  execution-time limits and do not host a long-lived WebSocket server for the duration of a multi-turn voice call.
  `web/` keeps the browser-facing page and mic/player UI; the actual audio relay needs a process that stays up for
  the call's duration.
- **Not in `mock_server`.** `mock_server` is explicitly the *mock* external-services surface
  (`AGENTS.md`: "mock_server/ — the mock external services the platform agent calls"). Gnani and the AgenticOrg
  chat API are both real, not mocked; folding a real voice relay into the mock module would misstate what that
  module is and blur a boundary `AGENTS.md` draws deliberately.
- **So: a new, small, stateless service**, `voice_bridge/` at the repo root, deployed as a second Deployment/Service
  in the **same** `kirro` namespace and cluster as `kirro-mock` (reusing the existing Traefik ingress controller and
  TLS setup, not a new stack), under its own hostname (`voice-kirro.<cluster-domain>`). This is the "new top-level
  service" `AGENTS.md` gates on an ADR — this is that ADR. Unlike `kirro-mock`, it holds no state between calls
  (no SQLite, no PVC), so it can run with more than one replica if needed later; one call is handled per WebSocket
  connection and nothing survives a restart or crash mid-call beyond that one call.

### Driving the agent: the session-cookie constraint already documented

AgenticOrg's own SDK auth (`Authorization: Bearer <api_key>`) needs an API key, and API keys are admin-only
(`/api/v1/org/api-keys` → `403 Missing scope: agenticorg:admin`, confirmed in `platform-map.md`). The only reachable
path is the same one `docs/agenticorg/platform-map.md` documents for the chat panel: sign in with an AgenticOrg
email/password, then `POST /api/v1/chat/query {"query": "...", "agent_id": "<uuid>"}` with the session cookie. The
voice bridge does this itself — signs in once, keeps the session, re-authenticates if it expires — rather than a
human keeping a browser tab open.

**Known limitation, carried over from the chat-panel findings and unresolved by this ADR:** `chat/history` is one
flat thread per `(user, agent)` pair with no conversation id. Every call the bridge places continues the same
thread as every other call under that login. The bridge therefore serializes calls — one active call at a time,
queue or reject a second — until AgenticOrg exposes a per-conversation chat endpoint or a dedicated login per call
becomes available. This is a real product constraint for a multi-user demo, not just an implementation detail.

## Consequences

- A third top-level service in this repo (`mock_server`, `web`, now `voice_bridge`), each independently deployed.
  `voice_bridge` is Python (FastAPI, matching `mock_server`'s stack and `gnani-vachana`'s native language), ships in
  the same container registry/workflow pattern as the mock (`ghcr.io/cheetos-gif/kirro`, a second entrypoint) to
  avoid standing up new CI.
- The AgenticOrg login used by the bridge needs to live as a Kubernetes Secret (`AGENTICORG_EMAIL`,
  `AGENTICORG_PASSWORD`), never in `.env` or git. Every call the bridge places is attributed to that one account in
  AgenticOrg's own Audit Log — acceptable for a competition demo, flagged as a real limitation for anything beyond
  it.
- Twilio's `make_call`/`send_sms` tool functions and the `twilio_kirro` connector stay registered (useful for
  outbound notification later, per `agent-spec.md`'s optional WhatsApp/SMS leg) but are **not** used for the call
  leg itself; no Twilio phone number is purchased.
- `docs/agenticorg/platform-bugs.md` Bug 3 is updated: the blocker is unchanged (no admin, no Gnani on the native
  voice platform), but the resolution path is now "build the browser bridge" rather than "needs admin or a paid
  phone leg."

## Open items

All three are now resolved, and by ADR-017 rather than by the mechanism this ADR described:

- **AgenticOrg login credential** — in hand, in the gitignored `.env`, verified working
  (`POST /api/v1/auth/login`, then `GET /api/v1/auth/me` returns the `developer` account).
- **Client-side resampling** — no longer KIRRO's problem. LiveKit's browser SDK captures and encodes
  the microphone; the `AudioWorkletProcessor` this ADR proposed was deleted with the relay.
- **Concurrency** — unchanged, and still the real constraint: one call at a time, because
  AgenticOrg's chat API has no conversation id and the worker shares one login. Enforced by
  `replicas: 1` on the worker (ADR-017).
