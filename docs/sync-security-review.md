# Sync security review

## Implemented

- Pairing code: 256-bit random opaque token, SHA-256 hash at rest, one-use, default 10-minute TTL
  (1–15 minutes configurable), old unused codes revoked when issuing a replacement.
- Brute-force protection: five invalid attempts per source address within 15 minutes trigger a
  15-minute lockout; source address is hashed at rest. Invalid, expired, used, and revoked codes
  share a generic response.
- Device credential: random per-device bearer token returned only once; only its hash is persisted.
  Device endpoints authenticate bearer token and reject revoked devices. Android stores the
  credential encrypted with AES-GCM and an Android Keystore key; no custom TLS trust manager or
  cleartext opt-in was found in the inspected Android source.
- Admin APIs use `X-Sync-Admin-Key`, minimum 32 characters, constant-time comparison. Without a
  configured key they are available only to loopback development/test. The frontend keeps the key
  in React memory and does not persist it.
- Remote sync routes reject HTTP; loopback/test can use local HTTP. Android independently enforces
  HTTPS and the system trust store.
- Normal Web data APIs are local-only in the backend principal dependency. `/health`, generated
  OpenAPI/Swagger/ReDoc metadata are public; they do not expose personal records. Extension and
  learning-content sync retain their own token guards.
- Push events are device-scoped, append-only and idempotent by globally unique `request_id`; changed
  content under an existing ID conflicts. Verified answers and SRS projections are not modified by
  review-event upload.
- Token values are not included in application response logging code. Pairing/device routes do not
  log credentials.

## Deployment constraints

- Do not expose backend development server directly to the Internet. Use a private HTTPS proxy with
  valid Android-trusted TLS. Never disable certificate validation or assume self-signed cert trust.
- If a reverse proxy fronts FastAPI, configure trusted proxy headers only for that proxy, block direct
  access to the upstream, and ensure remote Web API calls cannot appear as loopback. Expose remote
  pairing admin only with `SYNC_ADMIN_KEY`; otherwise keep operator UI/API private.
- Restrict CORS to explicit origins. Do not place admin key in query strings, browser storage, or
  screenshots. Rotate it through deployment configuration if disclosed.
- Pairing rate limits key off the network address FastAPI observes. A proxy deployment must preserve
  source identity safely; do not trust arbitrary client-supplied forwarded headers.

## Verification and known limits

Automated backend tests exercise one-use/expiry/wrong code, lockout, remote HTTP rejection, admin
auth, device revoke, missing device bearer, and observed pull/push activity. This does not constitute
live TLS or physical-device verification. There is no login system by design; access to the personal
Web interface must remain local/private. Repeated failed pair attempts and server activity metadata
are retained to support abuse protection and operational visibility.
