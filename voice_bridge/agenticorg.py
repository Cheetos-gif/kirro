"""Drives the "Kirro Declare" agent over AgenticOrg's chat API (ADR-016).

The platform's own SDK authenticates with an API key, but API keys are `agenticorg:admin`-only
(`/api/v1/org/api-keys` answers `403 Missing scope`, `docs/agenticorg/platform-map.md`). The only
reachable path is the one the dashboard's own chat panel uses: sign in with an email and password
for a cookie session, then POST the message to `/api/v1/chat/query`.
That session is therefore shared by every call the bridge places. Conversations are keyed by
`thread_id` (ADR-017): the platform's own chat panel sends the last reply's `thread_id` back on each
turn, and a turn sent without one starts a brand-new conversation. `AgentChat` tracks it per
instance, which is per call (`voice_bridge/agent.py` builds one `AgentChat` per job).
"""

from __future__ import annotations

import asyncio
import logging

import httpx

log = logging.getLogger("voice_bridge.agenticorg")

# The platform requires the CSRF header to echo this cookie on state-changing requests.
CSRF_COOKIE = "agenticorg_csrf"


class AgentChatError(RuntimeError):
    """The platform refused the login or the message."""


class AgentChat:
    """A logged-in chat session against one AgenticOrg agent."""

    def __init__(
        self,
        *,
        base_url: str,
        email: str,
        password: str,
        agent_id: str,
        timeout_s: float = 180.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._email = email
        self._password = password
        self._agent_id = agent_id
        self._client = client or httpx.AsyncClient(base_url=base_url, timeout=timeout_s, follow_redirects=True)
        # One message at a time: the agent's context is shared, and interleaving two turns would
        # interleave two callers' declarations into one conversation.
        self._lock = asyncio.Lock()
        self._logged_in = False
        # The conversation. `chat/query` starts a brand-new thread when this is absent, and a new
        # thread means the agent has no idea what was just said — the platform's own chat panel
        # sends it back on every turn (`assets/ChatPanel-*.js`: `...R ? {thread_id: R} : {}`) and
        # stores `r.data.thread_id` from each reply. The first response hands one out.
        self._thread_id: str | None = None

    @property
    def thread_id(self) -> str | None:
        return self._thread_id

    def start_new_thread(self) -> None:
        """Forget the conversation. One call is one thread; a new call must not inherit the last
        caller's declaration."""
        self._thread_id = None

    async def aclose(self) -> None:
        await self._client.aclose()

    def _csrf_fields(self) -> tuple[dict[str, str], dict[str, str]]:
        """CSRF arrives as a cookie named `agenticorg_csrf`.

        Empirically the header form alone is rejected (`403 CSRF token mismatch`) — the cookie is
        scoped to `/api/v1/auth`, so it is not on the `/api/v1/chat/query` request for the server to
        compare against. The `csrf_token` body field is what the platform accepts; both are sent.
        """
        token = self._client.cookies.get(CSRF_COOKIE)
        if not token:
            return {}, {}
        return {"X-CSRF-Token": token}, {"csrf_token": token}

    async def login(self) -> None:
        response = await self._client.post(
            "/api/v1/auth/login", json={"email": self._email, "password": self._password}
        )
        if response.status_code != 200:
            raise AgentChatError(f"AgenticOrg login failed: {response.status_code} {response.text[:200]}")
        self._logged_in = True
        log.info("agenticorg session established for %s", self._email)

    async def ask(self, text: str) -> str:
        """Send one user turn, return the agent's reply text.

        The turn continues whatever conversation this client is in; the first reply creates it.
        """
        async with self._lock:
            if not self._logged_in:
                await self.login()
            reply, status, thread = await self._post(text)
            if status in (401, 403):
                log.info("agenticorg session expired; re-authenticating")
                await self.login()
                reply, status, thread = await self._post(text)
            if status != 200:
                raise AgentChatError(f"chat/query failed: {status} {reply[:200]}")
            if thread:
                self._thread_id = thread
            return reply

    async def _post(self, text: str) -> tuple[str, int, str | None]:
        headers, extra = self._csrf_fields()
        body: dict[str, object] = {"query": text, "agent_id": self._agent_id, **extra}
        if self._thread_id:
            body["thread_id"] = self._thread_id
        response = await self._client.post("/api/v1/chat/query", json=body, headers=headers)
        if response.status_code != 200:
            return response.text, response.status_code, None
        try:
            data = response.json()
        except ValueError:
            raise AgentChatError("chat/query returned a non-JSON body") from None
        answer = data.get("answer") or data.get("text") or ""
        return str(answer).strip(), response.status_code, data.get("thread_id")
