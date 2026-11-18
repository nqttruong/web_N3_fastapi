# Android–Web JLPT data mapping

| Concept | Android Room | Web PostgreSQL/API | ID / time conversion | Ownership |
|---|---|---|---|---|
| Exam | exam_sets, exam_sections, exam_questions, exam_passages; remote copies in synced_* | exams, questions, passages | Remote UUID prefixed jlpt: in Android mirror; Android local set IDs have no server mapping | Web owns synced mirror; local bundled exam remains Android-owned |
| Attempt | exam_attempts, exam_attempt_items | exam_attempts | Android local string ID ↔ Web UUID mapping absent; Android started_at/submitted_at epoch ms ↔ ISO UTC timestamp | Each client owns attempts it creates; Web has no Android upload yet |
| Answer | exam_answers, immutable submitted exam_attempt_items snapshot | attempt_answers | Choice index Android 0-based; Web API 1-based; feed Android uses 0-based selected_index | Web/server snapshot owns Web grade; no Android push |
| Mistake | error_records numeric local ID, unique question | Derived grouped query over wrong Web attempt_answers | No stable Android mistake ID or stable mapping; aggregate key Web question UUID | Android state Android-only; Web occurrence aggregate derived |
| JLPT analytics | getGradedHistory() / dashboard calculations | /analytics/jlpt | No analytics row or cross-device ID; recomputed from source answers | Derived per client; Web report covers Web data only |
| Explanation | synced_explanations | ai_explanations | Web UUID namespaced in Android mirror | Web approved/current explanation authoritative |
| Review event | synced_review_events.request_id (UUID) | android_review_events.request_id unique | Android millis serialized as ISO UTC; server records device ID | Append-only event, retry idempotent |

All Android IDs remain separate from Web IDs except when the row is a Web mirror. Never
deduplicate exams by title. No table, FK or trigger change is needed for this Web feature
set; migration is not added.

Web's attempt answer stores selected choice and the correct answer snapshot at submission.
It does not overwrite today's verified key if that key changes later. Wrong notebook grouping
uses answer snapshots and only considers is_correct = false; blanks and ungraded responses
are separate outcomes.
