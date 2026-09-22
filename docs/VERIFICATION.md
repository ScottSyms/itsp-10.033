# Manual verification (spec S26)

This documents a manual comparison of representative final Canadian records against both the
live NIST OSCAL catalogue and the live Cyber Centre ITSP.10.033/ITSP.10.033-01 pages, performed
against a full real build (fetched 2026-09-22):

- NIST SP 800-53 Rev. 5 OSCAL: `metadata.version` 5.2.0, `oscal-version` 1.2.2, resolved commit
  `78650f02ad9321bb7b817846f8fbd4f2bcd620de` from `usnistgov/oscal-content`.
- All 20 ITSP.10.033 family pages and the ITSP.10.033-01 Medium-profile page, fetched live.

Full build result: 1,248 catalogue records (330 base + 918 enhancements) -- 145
`verified_inherited`, 915 `verified_modified`, 136 `verified_reclassified`, 52
`verified_canada_only`, 0 `unresolved`.

Every record below was cross-checked against `itsp-kb show <id>` output, the reconciliation
record in `data/output/reconciliation/records.jsonl`, and the live Cyber Centre page/live NIST
OSCAL object.

## AC-01 -- Access control policy and procedures

| Field | Value |
|---|---|
| NIST OSCAL id | `ac-1` |
| Canadian id | `AC-01` |
| Classification | Cyber Centre labels this **Activity** (NIST has no "activity" concept -- all SP 800-53 items are controls) |
| Origin / status | `nist_reclassified_activity` / `verified_reclassified` |
| Statement | 3 top-level items, 7 ODPs extracted from `[Assignment: ...]`/`[Selection (1 or more): ...]` brackets |
| Discussion | present, modified from NIST's guidance prose |
| GC discussion | none |
| Related | IA-01, PM-09, PM-24, PS-08, SI-02, SI-12 (6) |
| References | 3 (TBS Directive on Security Management Appendix E, cyber threat environment intro, TBS risk management guide) |
| Enhancements | none (matches the live page's explicit "Enhancements: None") |
| Field diffs | title, statement_text, discussion, odp_count, related all `modified` (this is the general-policy-and-procedures pattern repeated per family -- Canadian text substantially restates NIST's) |
| Medium profile | selected, placeholder values `C.1 C.2 frequency [at a frequency no longer than annually]` |

Confirms: reclassification logic correctly flips a NIST control to a Canadian activity without
losing the NIST lineage (`nist_oscal_id` stays `ac-1`).

## AC-02 -- Account management

| Field | Value |
|---|---|
| NIST OSCAL id | `ac-2` |
| Canadian id | `AC-02` |
| Classification | Control (both sides agree) |
| Origin / status | `nist_modified_canada` / `verified_modified` |
| Statement | 12 top-level items (a-l), 10 ODPs -- matches NIST's own ODP count (`odp_count: same`) |
| Discussion | present, `modified` |
| GC discussion | none |
| Related | 28 ids incl. AC-03, AC-05, AC-06, AC-17, AC-18, AC-20, ... -- `related: same` as NIST |
| References | 3 |
| Enhancements | 13 (`AC-02(01)`..`AC-02(13)`), all present on the live page |
| Field diffs | title `formatting_only` ("Account Management" vs "Account management"); statement_text and discussion `modified`; odp_count and related `same` |
| Medium profile | selected, placeholder `(J) frequency [at a frequency no longer than monthly]` |

Confirms: a genuinely NIST-inherited-with-wording-changes record is correctly distinguished from
a naming-convention-only difference (title is `formatting_only`, not counted toward `modified`
by itself) while the real statement/discussion rewrites are.

## CA-02 -- Control assessments

NIST `ca-2` -> Canadian `CA-02`, reclassified as an **Activity** (`verified_reclassified`). Has a
genuine **GC discussion** section (Government-of-Canada-specific text, confirmed Canada-only per
`canada_only_fields`), 3 enhancements, and `related` is `modified` relative to NIST (the Cyber
Centre's related-control list differs from the NIST OSCAL `rel="related"` links). Selected in the
Medium profile.

## CP-09 -- System backup

NIST `cp-9` -> Canadian `CP-09`, stays a **Control** on both sides (`verified_modified`). 5
top-level statement items, 4 ODPs matching NIST's count, 8 enhancements. `related` includes
`SA-400` -- a live cross-reference from a NIST-backed control to a Canada-only 400-series
control, confirming related-id extraction doesn't restrict itself to NIST-recognized ids.

## PL-10 -- Baseline selection

NIST `pl-10` -> Canadian `PL-10`, reclassified as an **Activity**. Single-statement-item control
with **no ODPs** (confirms the pipeline doesn't fabricate ODPs when none exist) and a **GC
discussion** section. `statement_text` is `formatting_only` relative to NIST (near-verbatim) while
`discussion` is genuinely `modified`. 9 references -- the highest reference count spot-checked.

## PM-01 -- Information security program plan

Representative PM-family record. NIST `pm-1` -> Canadian `PM-01`, reclassified as an Activity.
**Not selected** in the Medium profile (`selected: False`) -- confirms unselected rows are
captured accurately, not just selected ones.

## PT-01 -- Personal information handling and transparency policy and procedures

Representative PT-family record. NIST `pt-1` -> Canadian `PT-01`, reclassified as an Activity.
7 ODPs, and *every* diffed field (title, statement_text, discussion, odp_count, related) is
`modified` -- the PT family's privacy-specific framing diverges from NIST's PM/PT split more than
most families. Not selected in the Medium profile.

## SR-01 -- Supply chain risk management policy and procedures

Representative SR-family record. NIST `sr-1` -> Canadian `SR-01`, reclassified as an Activity, 7
ODPs, 7 references.

## SA-400 -- Sovereignty and jurisdiction (Canadian 400-series base record)

No NIST counterpart (`nist_oscal_id: null`, `origin: canada_only`, `status:
verified_canada_only`). Full statement, discussion, and 9 enhancements (`SA-400(01)` ..
`SA-400(09)`) parsed entirely from the Cyber Centre page -- there is nothing to reconcile against.
Related to AT-02, CA-02, RA-01, RA-02 (all NIST-backed controls, confirming a Canada-only record
can legitimately reference NIST-backed ones). Selected in the Medium profile.

## AC-17(400) -- Remote access: Privileged accounts remote access (Canadian 400-series enhancement)

An enhancement of a NIST-backed base control (`AC-17`, itself `nist_modified_canada` /
`verified_modified`, requirement kind Control on both sides) whose *own* enhancement number is
Canada-only. `origin: canada_only`,
`is_canadian_specific: true`, `parent_id: AC-17`. This is the case that originally exposed a real
bug during development: a first implementation only checked the enhancement's own number against
the 400 threshold and missed inheriting Canada-only status from a Canada-only *base* (see
`SA-400(01)`..`(09)` above); `AC-17(400)`'s parent is NIST-backed, so it exercises the *other*
path (own number >= 400) through the same code. Selected in the Medium profile.

## Confirmed defects in the official source material (not itsp-kb bugs)

Found via `itsp-kb validate`, which checks statement-text bracket balance among other things:

1. **MA-04(05)** ("Non-local maintenance: Approvals and notifications"): item (a) reads
   `"...by [Assignment: organization-defined personnel or roles"` with the closing `]` missing
   entirely, while item (b) correctly closes its own bracket. Confirmed against the live page's
   raw HTML -- this is a typo in the published Cyber Centre document, preserved verbatim (per
   S2.3, authoritative text is never silently corrected).
2. **SC-30(03)** ("Concealment and misdirection: Change processing and storage locations"): the
   statement ends `"...at random time intervals]]."` with one stray extra `]`. Confirmed against
   the live page's raw HTML.
3. **Medium-profile table 4.5** has two different rows both labeled `CM-11(02)` -- one describes
   "Software installation with privileged status" (matches the main catalogue's real
   `CM-11(02)`) and the other describes "Automated enforcement and monitoring" (matches the main
   catalogue's real `CM-11(03)`, so this row is mislabeled in the profile document).
   `parse-profile` detects and warns on this exact duplicate-with-disagreement case per spec S8.3
   and keeps the first-seen row rather than silently picking one.

## Two records the source itself leaves ambiguous

**AC-12** and **PE-22** are rendered as `<p><strong>Activity/Control:</strong> ...</p>` rather
than committing to `Control` or `Activity`. Both are left as `requirement_kind: unknown` with the
full statement text still captured -- the pipeline does not guess a classification the source
itself didn't commit to.

## Withdrawn records

23 of the 330 base records are marked `Withdrawn: Incorporated into <other id>.` or `Withdrawn:
Moved to <other id>.` by the Cyber Centre (e.g. `AC-13` -> "Incorporated into AC-02 and AU-06.").
These are preserved (never deleted or reused) with `is_withdrawn: true` and the note captured
verbatim in `withdrawal_note`; when the corresponding NIST control is still active upstream, this
divergence itself is treated as a modification (`origin: nist_modified_canada`) rather than
silently ignored.
