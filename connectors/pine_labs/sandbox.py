"""Pine Labs P3P sandbox connector (PINE_LABS_MODE=real). NOT IMPLEMENTED: no credentials yet.

Verified from PyPI package pinelabs-online-p3p-server-sdk 1.3.0 (import: pinelabs_p3p_server), read on
2026-10-01. These are real names in that package; nothing here is guessed:
  - server instance methods: create_mandate(CreateMandateOptions), get_mandate(mandate_id),
    get_mandate_balance(MandateBalanceLookupOptions{authorizationId|phoneNumber, paymentMethod}),
    revoke_mandate(CreateMandateRevokeOptions{paymentMethod, paymentMethodReferenceId}),
    capture(CaptureOptions{token, amount, paymentMethod, idempotencyKey}),
    create_refund(order_id, CreateRefundOptions{merchantOrderReference, orderAmount})
  - REST paths the SDK uses: POST /mpp/v1/pre-authorize, GET /mpp/v1/authorization/{id},
    GET /mpp/v1/balance, POST /mpp/v1/revoke, POST /api/pay/v1/refunds/{order_id}
  - sandbox base URL constant P3PEnvironment.SANDBOX = https://pluraluat.v2.pinepg.in
  - config needs clientId, clientSecret, merchantId (mandatory), paymentGateway, availablePaymentMethods
  - the client SDK no longer creates mandates; it creates a payment TOKEN (client.methods.create_token,
    bound to a 402 challenge id). capture() on the server consumes that token. So "charge against a
    mandate" is a two-party flow (server challenge -> client token -> server capture), not one call.

TODO(credentials): implement `PineLabsSandboxConnector.call` by mapping KIRRO operations
  create_mandate -> server.create_mandate, get_mandate_balance -> server.get_mandate_balance,
  release_mandate -> server.revoke_mandate, execute_charge -> challenge+token+capture (see above),
  refund -> create_refund. Add pinelabs-online-p3p-server-sdk to pyproject only when implementing.
  Confirm the response field names on the first sandbox call and update connectors/mock_schemas.py.
"""

from __future__ import annotations

from connectors.base import NotConfiguredConnector


def build_sandbox_connector(env: dict) -> NotConfiguredConnector:
    missing = [k for k in ("PINELABS_CLIENT_ID", "PINELABS_CLIENT_SECRET", "PINELABS_MERCHANT_ID") if not env.get(k)]
    reason = (
        f"missing env: {', '.join(missing)}"
        if missing
        else "real Pine Labs connector not implemented yet; see connectors/pine_labs/sandbox.py TODO"
    )
    return NotConfiguredConnector("pine_labs.p3p.sandbox", "pine_labs", reason)
