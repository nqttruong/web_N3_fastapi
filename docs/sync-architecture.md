# Sync architecture (PR6.1)

The FastAPI service is the content publisher and the Android app is an offline mirror. Device
pairing credentials are device scoped. A pull writes only the `synced_*` Room tables; it never
writes `learning_progress`, `review_records`, or bundled vocabulary/kanji/grammar tables.

## Feed consistency

PostgreSQL triggers store an immutable payload snapshot in `sync_changes` in the source
transaction. Cursor allocation calls `next_sync_cursor()`, which takes a row lock on the singleton
`sync_cursor_lock` until commit. This serializes allocation and commit order, avoiding a client
checkpoint passing a transaction that has allocated a lower sequence value but commits later.
Snapshots make each page replayable even if the source row changes while the client is paging.
Android applies one page and its `next_cursor` in one Room transaction.

The feed covers exam, passage, question, attempt, attempt answer, knowledge item, review item, and
Android review event changes. Question/knowledge links produce a fresh knowledge snapshot with
the linked question IDs. Deletes are tombstones. Approved explanations are exposed only when the
explanation content hash still matches its question. A now-unapproved or stale explanation is
published as a tombstone for the mirror.

## Conflict and retention rules

The Android content IDs are prefixed with `jlpt:` and stored in separate tables. Review item
metadata can refresh remotely, but its device-local schedule columns are preserved. Offline
JLPT review events use UUID `request_id`s and stay in an append-only Room outbox until the server
acknowledges them. Upload retries are safe because the backend inbox is unique on `request_id`.

## Transport

The Android client requires HTTPS and uses platform TLS verification. Pairing key is sent only to
the configured HTTPS endpoint; the returned device bearer token is encrypted with Android Keystore.
Do not expose the local API directly to the Internet. For emulator or physical device testing,
use a trusted HTTPS development endpoint reachable on the private network. Android emulator
`10.0.2.2` is the host loopback alias, but the app intentionally does not accept plain HTTP.
