# Android sync capability matrix

Status is based on Android source inspection at HEAD `07f0d0bfd84086cc322d30b8bd4ce89b59222a92`.
Android repository was read-only; no Gradle tasks were run.

| Data | Android schema/source | Android → Web | Web → Android | IDs / time / conflict | Status |
|---|---|---|---|---|---|
| Device identity | Settings + encrypted `android_sync` preferences | Pair credential | Credential returned once | Per-install token; bearer hash server-side; revoke invalidates token | Supported and integration-tested; device verification pending |
| Web exams | `SyncedExamEntity` / Room DAO | No upload | `/sync/changes` | Stable Web UUID; cursor snapshots; Web owns content | Supported and tested |
| Passages | `SyncedPassageEntity` | No upload | `/sync/changes` | Stable Web UUID; FK to exam; tombstones | Supported and tested |
| Questions / verified answers | `SyncedQuestionEntity` | No upload | `/sync/changes` | Stable Web UUID; answer index converted at boundary; verified only | Supported and tested |
| Approved explanations | `SyncedExplanationEntity` | No upload | `/sync/changes` | Web approval + matching content hash authoritative; stale becomes tombstone | Supported and tested |
| Web attempts / answers | `SyncedExamAttemptEntity`, `SyncedAttemptAnswerEntity` | Android-created local attempts are not uploaded | `/sync/changes` mirror only | Web UUIDs; answers are snapshots; append-only Web source | Supported and tested for pull; not bidirectional |
| Knowledge / review items | `SyncedKnowledgeEntity`, `SyncedReviewItemEntity` | No entity upload | `/sync/changes` | Stable Web UUID/version; archived status retained | Supported and tested |
| Review events | Existing `ReviewRecordEntity` history and JLPT event outbox | `/sync/push` | Event feed metadata only | Stable UUID `request_id`; append-only; retry idempotent | Supported and integration-tested |
| Android vocabulary learning progress / SRS projection | Existing Room `learning_progress`, `WordsReciteRecord` | No snapshot/upload API | Not published to these tables | Must preserve Android ownership; no overwrite | Android change required |
| Saved words | Android local saved-word entities | No upload API | Not recognized as a sync entity | No verified ID mapping/merge semantics | Android change required |
| Android-authored exam attempts and answers | Local Room exam/history records | No upload API | Web does not send them as Android-owned records | Local IDs and score lifecycle are app-specific | Android change required |
| Mistake notebook | Local error/mistake records derived from attempts | No upload API | Not recognized by the pull mapper | Derived/state semantics not synchronized | Android change required |
| JLPT analysis | ViewModel/repository-derived aggregates | No source event upload | Not a sync entity | Recompute only from source attempts/answers | Not supported as sync data |
| Static lesson packs | Git-tracked JSON Android assets | Not device sync | Separate Web source scanner/importer | Pack/entity IDs, source commit/hash, license gate | Backend source import only; no progress sync |

### Protocol safeguards

- Device endpoints `/sync/changes`, `/sync/push`, and `/sync/disconnect` require a non-revoked
  bearer credential. Pairing is one-time and rate-limited. Admin routes require operator access.
- Android recognizes only its implemented entity types; the server does not alias unsupported data
  to a known entity. A page failure leaves the Room cursor unchanged.
- Android→Web attempts/mistakes/analytics: **Backend ready — Android client change required.** No
  receiver is treated as evidence of device support.
- Web→Android for local Android progress/saved words is not enabled. No Android SRS table is changed.
