# V3.1 — N3.pdf inventory and content gap audit

Initial audit performed on 2026-11-17; re-audited on 2026-11-18 against the repository-root `N3.pdf`, current Android source at commit `64abb74f1f2d70a941aba67e3c9c47f59ec513b2`, and the configured Web database. Android was only read. The 2026-11-18 pass added one evidence-backed Web-side Kanji example mapping through the official source importer; it did not change Android assets or stable IDs.

## File and extraction

- 8,141,690 bytes; SHA-256 `97e73c6626a3d76246c4f70474440245b97415cc3caff04f8f2edb5df60f1ede`.
- Read-only comparison with `/media/truong/01DBB45ECE0C4E001/app/N3 Sensei/N3.pdf` found the exact same byte length and SHA-256, confirming the Web audit file is the Android-referenced PDF.
- Chromium-generated, unencrypted, 290-page A4 PDF.
- `pdftotext -layout` extracted text from all 290 pages; none of the pages had an empty text layer. OCR was not needed for text presence. Visual verification of every individual chart/image was not performed.
- The cover says 2,726 Anki cards. The table of contents separately lists source lesson/group counts; these are not the same measure as generated Anki cards.

## Table-of-contents inventory

| Content | Groups | TOC item counts | Total shown |
|---|---:|---|---:|
| Vocabulary (未来) | 22 | 43, 40, 39, 50, 50, 38, 40, 60, 40, 50, 48, 40, 40, 45, 40, 40, 42, 40, 13, 61, 30, 20 | 909 |
| Kanji | 2 | 98, 97 | 195 |
| Grammar | 6 headings present | 6, 4, 19, 30, 20, 77 | 156 |

The grammar contents jump from section 03 to section 05. Section 04 is absent from both the extracted PDF text and its contents list. The 156 figure is therefore the sum of the six sections that are present, not evidence that this is a complete N3 grammar syllabus.

The PDF’s internal cover total (2,726 Anki cards) must not be reported as 2,726 distinct learning items. The group counts above are the auditable inventory available from the PDF contents list.

## Current Web database snapshot

Read-only query of the configured development database on 2026-11-17:

| Entity | Active rows |
|---|---:|
| Learning content packs | 5 |
| Vocabulary | 880 |
| Kanji | 393 |
| Grammar | 64 |

These are aggregate counts across existing sources. The Android read-only asset `n3-kanji.json` contains exactly 393 unique verified Kanji records, each with source pages in the Kanji section (122–255); the Web has the same 393 records. This is a verified pack-to-Web identity/count parity, but not a claim that the PDF’s 195 TOC flashcard count equals 393 unique focus Kanji.

The Android `n3-grammar.json` has 174 grammar records: 64 records have per-card `n3pdf-g-*` provenance and 110 original records have `vnjp-np-*` source IDs. The Web now contains all 174 stable IDs. The 110 originals were imported for the owner's private Web instance under source-specific private-use declarations; this does not assert public redistribution rights or professional review. The raw PDF has 156 listed grammar cards across six groups, so 92 listed cards do not have an approved PDF-derived item mapping. Group 04 is absent from the PDF itself.

The stable-ID check found exact equality for Kanji (393/393 IDs and characters) and all Grammar IDs (174/174). All 64 approved PDF grammar refs `n3pdf-g-*` and 110 original refs `vnjp-np-*` match the Web rows; all 393 Kanji item IDs/characters match Android. Public aggregate gap counts are in [`v3-1-grammar-gap-review-summary.md`](v3-1-grammar-gap-review-summary.md); candidate-level source text is kept out of this public repository.

The 92 rows without an approved N3.pdf item mapping have now been classified one by one from Android `docs/data/n3-grammar-pdf-mapping.tsv` and `n3-grammar.json`:

| Classification | Rows | Decision |
|---|---:|---|
| Exact match to an existing Mimikara candidate | 57 | Candidate IDs/patterns exist, but every candidate source is `licenseVerified=false`; do not import as approved N3.pdf content. |
| Same pattern family, distinct variant/explanation | 24 | Candidate IDs exist, but do not merge or overwrite automatically; candidate source remains unverified. |
| Comparison card, not a standalone grammar item | 11 | Keep referenced component patterns; do not create an item for the comparison card. |
| **Total** | **92** | **No unclassified rows remain; zero new grammar items were created from these 92.** |

The other 64 PDF rows (58 “mục riêng” plus 6 “liên quan, khác cách dùng”) already have per-card source declarations and stable IDs. Grammar group 04 is absent from the PDF contents and text layer; it was not synthesized. Candidate-level source details remain in the private working copy and are not redistributed here.

Grammar gaps by PDF group:

| PDF group | Cards in PDF | Approved stable item IDs in Android/Web | Not mapped |
|---|---:|---:|---:|
| 01 | 6 | 1 | 5 |
| 02 | 4 | 1 | 3 |
| 03 | 19 | 5 | 14 |
| 04 | Absent | 0 | — |
| 05 | 30 | 12 | 18 |
| 06 | 20 | 14 | 6 |
| 07 | 77 | 31 | 46 |
| **Total present groups** | **156** | **64** | **92** |

Payload metadata audit and source reconciliation:

- Kanji: all 393 source rows have per-item page provenance and match the Android `docs/data/n3-kanji-meanings.tsv` exactly for Hán Việt, On'yomi, and Kun'yomi (0 field mismatches). 52 `kunReadings` arrays are explicitly empty and the corresponding TSV `kun` cells are empty; these are source absences, not fields to invent. 393/393 have Hán Việt and On readings; 341/393 have Kun readings.
- Kanji examples: current asset has 1,279 rows; 1,272 are from verified sources and 7 are from a source with `licenseVerified=false`. The seven unverified rows remain blocked. The approved Web snapshot initially contained 1,271 examples. Read-only reconciliation identified one extra verified example not linked by the content record; page and TSV provenance support a narrow Web-owned link to an existing stable item. The official scoped sync added exactly one example and updated only that Kanji item's provenance.
- Grammar: the 64 PDF-derived rows have source pattern, structure/formation and short meaning, with no linked examples. The 110 original grammar rows now have 220 linked examples imported under the private source-right declarations. A separate source contains 140 additional examples and remains unapproved/unpublished. Candidate-level text and line-level review notes remain in the private working copy; only aggregate counts are published.

Missing fields are reported as missing, not generated. The 110 original examples do not include furigana in the source and remain without it. The separate `n3-grammar-examples` source is not covered by the 110 private-use declarations; its 140 examples are not published or synthesized.

## Import and rights status

No separate parser/import of `N3.pdf` was run. The database has source-specific private rights for the 110 original Android Grammar sources, based on the owner's direct assertion for this private Web instance. The separate 140-example source and unmapped PDF cards remain outside that declaration. No public redistribution right is asserted; do not bypass source-specific rights checks.

## Before / after (2026-11-18)

| Check | Before | After | Result |
|---|---:|---:|---|
| Active Kanji items | 393 | 393 | Stable IDs unchanged. |
| Kanji Hán Việt / On / Kun parity with source TSV | Not rechecked in this pass | 393/393 Hán Việt; 393/393 On; 393/393 Kun-field parity, including 52 intentional source-empty values | No unsupported readings added. |
| Approved examples in Web `n3-kanji` pack | 1,271 | 1,272 | Added the one PDF/TSV-provenanced link `n3k-x-10-002`; stable item ID retained. |
| Learning progress rows | 20 | 20 | Preserved. |
| Active Grammar items | 64 | 174 | All stable IDs retained; existing progress rows preserved. |
| Unclassified grammar gap cards | 92 | 0 | 57 exact candidates, 24 variants, 11 comparison cards documented individually. |
| Grammar 04 / approved Grammar examples | Absent / 0 | Absent / 0 | No group or examples fabricated. |

Official source sync restored 110 Grammar items, added their 220 source-linked examples, and populated the 15 original Grammar lessons while retaining all 64 existing PDF items. A repeat sync returned `no_changes`; no duplicate item/example rows were created. All 10 existing Grammar progress rows and 19 Grammar study events remained unchanged. No PDF/source files or Android files were changed.
