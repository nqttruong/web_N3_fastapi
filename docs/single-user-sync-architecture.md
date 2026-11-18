# Single-user Android ↔ Web sync

## Identity and trust

This deployment has one personal Web profile and does not use email, password, or OAuth. Android is
identified by a per-installation device credential issued during pairing. The Web remains a local
operator interface; Android accesses only `/api/v1/sync/*` with its device bearer credential.

The operator creates a random pairing code from **Settings → Đồng bộ Android**. Codes are
single-use, stored only as SHA-256 hashes, expire after 10 minutes by default (at most 15), and
replace previous unused codes. Invalid/expired/reused codes return the same error. Five failed
attempts per source address in a 15-minute window cause a 15-minute lockout. A successful pair
issues a random per-device bearer token; PostgreSQL stores only its hash. Android encrypts the
token using an AES-GCM key held by Android Keystore.

## Sync flow

1. Operator issues a code and enters it once in Android Settings alongside the reachable HTTPS URL.
2. Android calls `POST /api/v1/sync/pair` with `X-Pairing-Key`; pairing alone is not data sync.
3. Android pulls pages from `/sync/changes` using its Room checkpoint. Its implementation validates
   and applies the page in a Room transaction and checkpoints only after application succeeds.
4. Android pushes review events to `/sync/push`. Events are append-only and idempotent by
   `request_id`; an identical retry is acknowledged as duplicate, conflicting reuse is rejected.
5. Backend records last authenticated request, pull, and push timestamps separately. These timestamps
   show observed API activity; they do not prove the client completed all pages or a complete sync.
6. Operator may revoke a device in Web Settings; the next authenticated Android request is rejected.

## Change feed and isolation

The feed publishes Web exams, passages, questions, current approved explanations, attempt and answer
mirrors, knowledge items, and review-item metadata. Verified answer snapshots are server-authoritative;
unverified answers are not published as correct. Stale or unapproved explanations become tombstones.
Android stores pulled data in separate `synced_*` Room tables. Checkpoints are device-local.

Android → Web currently supports review-event history only. It does not upload Android vocabulary
learning progress, `WordsReciteRecord`, saved words, locally authored exam attempts/answers, mistake
notebook state, or analytics. The static content-pack worker is a separate read-only source import,
not personal device sync.

## Network boundary

The Android source requires `https://` and uses the platform's normal certificate verification; it
does not install a custom trust manager or accept cleartext HTTP. Use a hostname covered by a
certificate trusted by Android (for example, a controlled domain with private DNS routing to the
LAN server). A self-signed certificate is not assumed to be trusted. Never disable verification or
expose the development server broadly to the Internet.

Configure `SYNC_ADMIN_KEY` with at least 32 random characters when the admin API can be reached
outside loopback. Admin operations use `X-Sync-Admin-Key`; the UI keeps the key in page memory only.
Other Web data APIs are local-only in the backend. When deploying behind a reverse proxy, ensure
the proxy does not make remote Web API requests appear to originate from loopback; expose only the
sync routes to the phone and keep the Web/operator API private. Configure proxy HTTPS forwarding
only from a trusted proxy.

## Operational state

Migration `0009` is additive: pairing-code and rate-limit tables plus per-device pull/push times.
It does not alter learning or exam data. See `android-sync-capability-matrix.md`,
`android-pairing-guide.md`, and `sync-security-review.md`.
