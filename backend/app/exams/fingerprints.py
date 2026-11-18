"""Content hashing for duplicate detection.

NFKC is applied **only** to the hash input, never to stored text. What NFKC does and does not
fold (verified by tests/test_fingerprints.py):

* folds: full/half-width ASCII & digits (Ａ→A, １→1), half-width katakana (ｱ→ア),
  ideographic space (U+3000) → space, compatibility forms such as ① → 1, ㈱ → (株)
* keeps distinct: hiragana vs katakana (あ ≠ ア), 長音符 ー vs hyphen/dash, different kanji,
  small vs large kana (っ ≠ つ), voiced marks (か ≠ が), furigana in brackets

Collisions caused by folding are acceptable for *flagging* duplicates; nothing is merged
automatically on a fingerprint match.
"""

import hashlib
import json
import re
import unicodedata
import uuid

_WS = re.compile(r"\s+")


def normalise_for_hash(value: str) -> str:
    return _WS.sub(" ", unicodedata.normalize("NFKC", value)).strip()


def _sha(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def question_content_hash(
    passage_id: uuid.UUID | None, question_text: str, options: list[str]
) -> str:
    """Per-exam uniqueness key (includes the passage)."""
    return _sha(
        {
            "p": str(passage_id) if passage_id else None,
            "t": normalise_for_hash(question_text),
            "o": [normalise_for_hash(o) for o in options],
        }
    )


def question_fingerprint(question_text: str, options: list[str]) -> str:
    """Cross-exam key (no passage). Must stay identical to migration 0002's frozen copy."""
    return _sha(
        {"t": normalise_for_hash(question_text), "o": [normalise_for_hash(o) for o in options]}
    )
