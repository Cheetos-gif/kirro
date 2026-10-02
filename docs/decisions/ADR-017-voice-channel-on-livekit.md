# ADR-017: The voice channel moves onto LiveKit, with Gnani's own LiveKit plugin

Status: accepted and implemented (2026-10-02). Amends ADR-016 — the browser channel and the reason
for it are unchanged; the hand-rolled relay it described is replaced.

## Context

ADR-016 built the browser call channel by hand: a custom `AudioWorkletProcessor` to resample the
microphone and cut it into 1024-byte frames, a bespoke WebSocket protocol between the page and a
FastAPI relay, manual scheduling of incoming PCM through `AudioBufferSourceNode`, and a canvas
visualiser. It worked (verified live end to end), but every one of those pieces is a solved problem
with a maintained library behind it, and the relay had to own concerns that are not KIRRO's:
reconnection, device changes, echo cancellation, interruption, and turn-taking.

The deciding fact: **Gnani publishes LiveKit and Pipecat plugins for exactly this.** `livekit-plugins-gnani`
wraps Gnani's STT and TTS into LiveKit's standard `stt.STT`/`tts.TTS` classes, and LiveKit's browser
SDK plus `@livekit/components-react` provide the microphone capture, playback, transport, and a
`BarVisualizer` — the visualiser an earlier request had asked for, implemented as a component rather
than by hand.

## Decision

Replace the custom relay with the standard stack on both sides.

- **Browser**: `livekit-client` + `@livekit/components-react` (`LiveKitRoom`, `RoomAudioRenderer`,
  `BarVisualizer`, `useVoiceAssistant`, `useTranscriptions`) in `web/`. The portal mints a
  short-lived access token in a server route (`/api/voice/token`) with `livekit-server-sdk`; the key
  pair never reaches the browser.
- **Worker**: `livekit-agents` (`AgentSession`) with `livekit-plugins-gnani` for speech and
  `livekit-plugins-silero` for local end-of-turn detection. `voice_bridge/agent.py` is the entrypoint.
- **The model stage is the AgenticOrg agent.** LiveKit's pipeline expects an `llm.LLM` between STT
  and TTS; KIRRO has no separate model. `voice_bridge/agenticorg_llm.py` adapts the existing
  `AgentChat` client to that interface — the newest user turn in, the agent's answer out. Only the
  newest utterance is ever sent, because AgenticOrg owns the dialogue state.
- **Transport**: a self-hosted `livekit-server` in the same `kirro` namespace (open source, no
  per-minute cost, no third-party account). The browser connects over WebRTC to
  `voice-kirro.upayan.dev` for signalling, and media goes directly to the node's UDP port.
- **Deleted**: `voice_bridge/relay.py`, `voice_bridge/gnani.py`, `voice_bridge/app.py`,
  `web/public/voice-worklet.js`, and the `/talk` component that drove them. The `websockets`
  dependency went with them.

## Consequences

- KIRRO's own surface for the voice channel shrinks to two files that are genuinely KIRRO's: the
  AgenticOrg LLM adapter, and the agent-entrypoint wiring. Speech, transport, playback, and the
  visualiser are the libraries' problem now.
- **A fourth Deployment** (`kirro-livekit`) and a fourth port set. Self-hosting is the cost of
  avoiding per-minute billing: WebRTC media cannot travel through an Ingress, so the browser has to
  reach the node's own ports — `7881/tcp` and `7882/udp`, opened in the cluster repo's
  `terraform/firewall.tf`. `7882/udp` is a single muxed port rather than LiveKit's default
  50000-60000 range, precisely so that firewall rule stays small.
- **The media ports are published by a `LoadBalancer` Service, not `hostNetwork`.** The obvious
  answer for a WebRTC server is `hostNetwork: true`, and it does not work on this cluster:
  namespace `kirro` enforces Pod Security `baseline`, which rejects host namespaces and hostPorts
  outright (the pod never schedules), and relaxing that to `privileged` for one pod would grant the
  permission to every workload in the namespace. k3s's ServiceLB binds the same port numbers on the
  node instead — the mechanism Traefik already uses for 80/443 here — which keeps the pod
  PSA-clean and still satisfies ICE, since ICE has no notion of port translation and the advertised
  port must be the listening port. That also means the room server's NetworkPolicy needs an
  `ipBlock` rule for the media ports: ServiceLB forwards with the *caller's* source address
  preserved, so there is no in-cluster source to match.
- Signalling is the only part that goes through the Ingress (`voice-kirro.upayan.dev`, port 443 like
  every other host), so `7880/tcp` is deliberately **not** opened on the firewall.
- LiveKit's cloud-only features degrade rather than break offline: the adaptive interruption
  detector fails its `401` against `agent-gateway.livekit.cloud` and falls back, and turn detection
  runs locally through Silero, whose model ships inside the plugin. No LiveKit account, no LiveKit
  API key beyond the self-hosted pair.
- The one-call-at-a-time constraint from ADR-016 still holds and is still enforced by `replicas: 1`:
  the worker drives a single AgenticOrg login whose chat history is one flat thread. LiveKit would
  happily run concurrent rooms; the bottleneck is AgenticOrg, not the transport.
- LiveKit keeps a local transcript for captions. That transcript is a display detail — it is not a
  second decision log, and nothing reads it back (ADR-011's "the brain lives on AgenticOrg" is
  untouched).

## Verification

See `docs/testing.md`. The end-to-end check joins a room as a caller, publishes synthesized speech
as the microphone track, and asserts the agent's audio and both transcriptions come back; the
Gnani and AgenticOrg integrations behind it are exercised by the same check rather than mocked.
