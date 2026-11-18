# Import fixtures

All Japanese content in these files was **written for this project** (self-authored N3-style
questions). Nothing is copied from dethitiengnhat.com or from official JLPT materials.

`dethitiengnhat_like_scored.html` reproduces only the *HTML structure* (class/id names) that
the real dethitiengnhat.com exam page uses after pressing "Tính Điểm", as observed on
2026-11-10 (see docs/parser-adapters.md). It also contains deliberately malicious markup
(script, event handlers, javascript: links, iframe) to test sanitising.
