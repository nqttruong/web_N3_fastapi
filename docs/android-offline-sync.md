# Android offline sync and device testing

## What is stored locally

Room schema 15 adds isolated `synced_*` tables and does not copy, delete, or rewrite existing
`learning_progress` or `review_records`. The 14→15 migration only creates the mirror, checkpoint,
and review outbox tables. No destructive migration fallback is configured. A downloaded page and
its cursor commit in one Room transaction; invalid payloads, unknown schema versions, out-of-order
cursors, or a failed write leave that page's cursor unchanged. Retry the same page after network,
app, or server restart. Tombstones mark mirror rows unavailable rather than removing learner
history.

Offline review of a JLPT AI Review item creates a UUID event and updates only that mirror item's
separate local schedule. Events remain pending through offline periods and are retried until the
server acknowledges them. Existing vocabulary SRS and review history use their original path.

Settings reports pairing, last successful pull, downloaded change count, pending events and the
last error; pairing by itself is not reported as a successful content sync. 401/403 indicates a
revoked or expired credential and requires pairing again.

## Emulator or physical phone

1. Start PostgreSQL and FastAPI behind a private HTTPS endpoint with a certificate trusted by Android.
   Do not expose the development API publicly. The app rejects `http://` and uses platform certificate
   validation; no custom trust manager was found in the Android source.
2. For an emulator, use `10.0.2.2` only behind a valid trusted HTTPS hostname/proxy. For a phone,
   use a LAN-reachable hostname covered by a trusted certificate. Do not substitute `127.0.0.1`, use
   HTTP, or assume self-signed certificate trust.
3. In Web **Settings → Đồng bộ Android**, create a one-time code. In Android Settings enter the HTTPS
   base URL and code, pair, then tap **Đồng bộ ngay**. Code expiry/revoke details are in
   `android-pairing-guide.md`.
4. Verify knowledge/questions/explanations offline,
   review an item with each rating, restart the app, then reconnect and confirm pending count
   falls. Revoke the test device server-side to verify the 401 path.

Android 16 emulators were started in this session. The full instrumented suite ran 372 tests
(369 passed, 2 skipped, 1 unrelated hour-picker UI failure). A focused run of Room migration and
sync integration classes then passed all 19 tests, including fake-transport tombstone handling.
These tests do not contact a live backend. No physical phone or trusted HTTPS development API was
available, so live backend pairing/upload/download remain unverified. Current Android push/pull scope
is listed in `android-sync-capability-matrix.md`; local exam history and Android learning progress
are not synced.
