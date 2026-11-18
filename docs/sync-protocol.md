# Sync protocol v1.0

All calls use `/api/v1/sync`; pairing and authenticated calls require HTTPS from Android.

## Pair and pull

`POST /pair` with `X-Pairing-Key` and `{ "device_name": "..." }` returns one opaque device
bearer credential. Store it in Android Keystore encrypted preferences; never log it. A revoked or
invalid device receives 401 and must pair again.

`POST /disconnect` with the device bearer revokes it server-side. Android removes its locally
encrypted bearer after attempting this call; if the device is offline, it reports local removal
while the server can only revoke the credential once reachable (or through operator action).

`GET /changes?cursor=<non-negative bigint>&limit=1..500` returns:

```json
{"data":{"data":[{"cursor":1,"entity_type":"question","entity_id":"uuid","operation":"update","version":2,"changed_at":"2026-01-01T00:00:00Z","schema_version":"1.0","data":{}}],"next_cursor":1,"has_more":false}}
```

The API returns immutable snapshots or a `data: null` tombstone. Entity types are `exam`,
`passage`, `question`, `ai_explanation`, `exam_attempt`, `attempt_answer`, `knowledge_item`,
`review_item`, and `android_review_event`. Android recognizes event-only `review_event` and
`question_knowledge` as feed metadata. Unknown types or schema versions are errors; the Android
page transaction and checkpoint roll back together. Pull pages from cursor 0 for bootstrap and
continue until `has_more=false`. The cursor is a serialized commit-order cursor, not an ordinary
PostgreSQL sequence exposed without transaction ordering.

Question `answer_index` and attempt answer indexes are zero based. `answer_verified` is true only
when an answer has verified provenance. Explanation payloads are present only when approved and
current for the question content hash. An explanation made stale/rejected after publication is a
tombstone. Knowledge status can be `active`, `archived`, or `merged`; review item status can be
archived and must not enter the active offline queue.

## Push review events

`POST /push` takes up to 500 events. `request_id` is globally idempotent: a retry with the same
content returns it in `duplicates`; reusing an ID for different content conflicts. Android sends
both existing vocabulary/kanji/grammar history and `JLPT_REVIEW_ITEM` events. The endpoint stores
an append-only inbox and does not alter server or Android SRS projections.

Times use ISO-8601 RFC3339 UTC. Android stores epoch **milliseconds** locally; conversion to and
from API instants occurs at the transport boundary. Duration fields are minutes.
