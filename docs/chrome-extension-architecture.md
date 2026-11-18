# Chrome Extension architecture

PR5 is a local Chrome Manifest V3 extension for importing a Dethitiengnhat N3 exam into the existing PR2 draft lifecycle.

## Components

- `extension/manifest.json`: popup, options page and module service worker. Runtime permissions are limited to `activeTab`, `scripting`, `storage`, `contextMenus` and `alarms`; a per-site optional permission is requested only when the user enables dictionary lookup for that host. Backend host permissions are loopback-only.
- `extension/src/popup/`: user-initiated extraction, summary, warnings, JSON preview and send action.
- `extension/src/content/extract.ts`: a serializable adapter injected into the active tab only after the user clicks Extract. It reads rendered exam DOM nodes and checked radio state; it does not evaluate site code or read cookies/storage.
- `extension/src/content/dictionary-helper.ts`: observes only an explicit text selection on a user-enabled host, shows an isolated hover popup, and sends only the selected text to the extension background.
- `extension/src/background/service-worker.ts`: health check and authenticated capture/save requests, exact dictionary lookup/cache, and persistent offline save retry; dictionary lookup does not open a Web tab.
- `extension/src/options/`: local frontend/backend URL and extension bearer-secret configuration.
- `extension/scripts/copy-static.mjs`: separate Chromium MV3 and Firefox MV3 package manifests; local builds output to `extension/dist-v3-1/`.
- `backend/app/imports/browser_capture.py` and `POST /api/v1/imports/browser-capture`: strict versioned payload validation and conversion to the standard editable PR2 draft.

The capture is limited to Dethitiengnhat N3 parts `/1` and `/3`. Listening (`/2`) is not supported. The adapter retains Japanese Unicode and serializes only whitelisted inline `<u>`, `<ruby>` and `<rt>` semantics in text fields; the backend editor displays original capture JSON as text, never as raw HTML.

## Trust and persistence

The extension's source URL is validated as metadata, not treated as proof of origin. The API requires both a configured shared bearer secret and a loopback TCP peer; CORS/Origin is not authentication. An idempotency fingerprint plus partial PostgreSQL unique index makes identical retry requests reuse the same draft. A capture never creates an exam directly. Source answer candidates are mapped to PR2 `site_answer`/`correct_answer`, always with `answer_confirmed=false`. The preview remains the point where a person checks content and explicitly commits it.

See [installation](chrome-extension-installation.md), [capture behavior](dethitiengnhat-capture.md) and [security](extension-security.md).
