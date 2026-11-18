# Android entity mapping

All remote content is isolated under a `jlpt:` ID namespace and separate Room tables. No server
record is merged into the bundled N3 Sensei content tables.

| Sync entity | Room mirror | Mapping / safety |
|---|---|---|
| `exam` | `synced_exams` | Server ID retained; level/category/status retained. |
| `passage` | `synced_passages` | `content` is exposed as `text`; exam ID is namespaced. |
| `question` | `synced_questions` | Four options are stored as a string list; only verified 0-based answer index is trusted. |
| `ai_explanation` | `synced_explanations` | Approved/current payload only; stale/rejected transitions tombstone the mirror. |
| `exam_attempt` | `synced_attempts` | Append-only attempt summary; ISO timestamps retained as UTC text. |
| `attempt_answer` | `synced_attempt_answers` | Composite attempt/question key, server ID retained for tombstones; answer indexes are 0-based. |
| `knowledge_item` | `synced_knowledge` | Details and linked question IDs are JSON snapshots; status/merge target retained. |
| `review_item` | `synced_review_items` | Remote metadata refreshes while local scheduler columns are preserved. |
| Android review event | `synced_review_events` | Append-only local outbox; UUID request ID, acknowledgement, attempts and error retained. |
| Feed checkpoint | `sync_checkpoints` | Schema version, cursor, last success/error, download count, separate from learning progress. |

`learning_progress`, `review_records`, `WordsReciteRecord`/legacy vocabulary progress and existing
exam entities are not targets of the pull mapper. Android's JLPT review queue uses a separate
local schedule and simple independent interval policy; it does not claim to be the backend's SRS
algorithm.
