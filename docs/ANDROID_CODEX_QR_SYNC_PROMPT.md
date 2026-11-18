# Copy into a separate Codex session opened on the N3 Sensei Android repository

You are a Senior Android Engineer. Implement QR pairing for N3 Sensei against the **existing** JLPT AI Review Web QR protocol v1 described in `docs/android-qr-sync-protocol.md` in the Web repository. First read that document and inspect the Android pairing screen, SyncRepository, Room tables/migrations, Keystore credential storage, network security policy, and tests. Do not infer the contract from this prompt alone. The Web backend has been mock-client tested, but live Android pairing has not been verified.

## Objective

Add an Android QR scanner and integrate it with the existing device pairing and sync lifecycle. Retain manual pairing as a fallback. Never reset Room or erase learning state, `learning_progress`, `WordsReciteRecord`, pending review events, or existing credentials before the new connection is confirmed. Do not use ChatGPT/OpenAI tokens.

## Protocol to implement

1. Scan QR only after the user explicitly opens pairing. Parse JSON with `version=1`, HTTPS `base_url` origin, UUID `session_id`, URL-safe `challenge`, timezone-aware `expires_at`. Reject malformed/expired/unsupported QR and loopback/HTTP URLs; do not disable certificate or hostname validation. Android must trust the server's certificate under its existing platform policy. Do not hardcode `127.0.0.1` or a development machine IP.
2. Show the HTTPS hostname and ask the user to continue. Generate a new cryptographically secure URL-safe random `device_credential` of at least 48 characters, store it in the existing Keystore-backed credential store with a pending status, and reuse it for retries of the same session. Never log, expose to UI, or send it to a site other than the validated origin.
3. POST `{base_url}/api/v1/sync/qr-sessions/{session_id}/claim` with `{challenge, device_name, device_credential}`. Parse wrapped `{data:{status,claim_ticket,confirmation_code}}`. Retry with the **same** body on network failure; do not create multiple device credentials. Handle `401/404/409/422/503` explicitly.
4. POST `/ready` with `X-Claim-Ticket`. Show the returned six-digit code and device name on Android. The human enters that code into Web Settings. Poll `GET /api/v1/sync/qr-sessions/{session_id}` with `X-Claim-Ticket` until `PAIRED` or a terminal failure/expiry. Poll at a modest interval, stop on cancellation/background as appropriate, and respect five-minute TTL. A scanned or claimed QR is **not** paired.
5. Once `PAIRED`, atomically mark the pending credential active for the matching server origin and `device_id`; then use `Authorization: Bearer <device_credential>` with the current SyncRepository. Do not discard the old connection or its outbox before the new connection works. Keep manual PR6 `POST /sync/pair` functional.
6. Pull existing compatible Web content via `GET /api/v1/sync/changes?cursor=...`, starting at 0 if no checkpoint. Validate schema/entity/payload, apply page and checkpoint in one Room transaction, paginate until `has_more=false`, preserve tombstones. Push existing append-only review events with stable request UUIDs to `POST /api/v1/sync/push`; remove from outbox only after accepted/duplicate acknowledgment. Retry safely offline. Display separate paired, pull, push, fully synced, revoked, expired, and offline states.
7. Support device disconnect/revoke through existing `POST /api/v1/sync/disconnect` and local credential cleanup while retaining Room learning data and past events. A revoked credential must not be silently reused.

The Web claim endpoint reuses the PR6 `sync_pairing_attempts` source-address limiter: five invalid pairing attempts in a 15-minute window lock that source for 15 minutes and return `429` with a `Retry-After` header. Handle the header as a pairing retry delay; do not generate a different credential or repeatedly retry in a tight loop. This is separate from the five wrong Web confirmation-code submissions that fail only that QR session.

## Scope limits

- Do not add upload of Android exam attempts, lesson progress, saved words, or mistakes unless a separately reviewed Web contract and conflict policy exists. QR changes pairing only; it does not magically enable new data types.
- Do not overwrite verified answers, legacy SRS fields, or unrelated Room tables. Add a forward-only Room migration only if the existing schema truly needs new persisted pairing state. Provide migration tests from every supported old version. Never use destructive migration.
- Never log QR challenge, claim ticket, confirmation code, device credential, or bearer header. Keep content scripts/WebViews out of the credential path.
- Keep network and app changes in the Android repository in that **separate session**. This Web V3 task must not modify Android.

## Verification required in the Android session

- Unit tests for QR parsing/validation, expiry, unsupported version, HTTPS/certificate behavior, state transitions, replay, retry and revoked credential.
- Fake transport + Room test DB integration for pairing, bootstrap/incremental pull, cursor rollback, duplicate changes, tombstones, offline event retry, and legacy data preservation.
- Migration test if schema changes. Run Android unit tests/build and instrumented tests where an emulator/device is available.
- With a reachable trusted HTTPS server, verify real emulator/device scan → claim → human code → confirm → pull → offline review → push → revoke. Record the exact environment and results. If this last step is unavailable, report **Android QR implementation tested locally; live device verification pending** rather than claiming live end-to-end sync.

Web-side API shapes, errors, existing change-feed fields, and a Mermaid sequence are in `docs/android-qr-sync-protocol.md`. Preserve compatibility with existing manual-pairing Android builds.
