# itsp-knowledge-base

A deterministic pipeline that builds a structured Canadian ITSP.10.033 knowledge base by combining:

1. the official **NIST SP 800-53 Rev. 5 OSCAL catalogue** as the pre-structured baseline for
   NIST-derived controls, enhancements, parameters, and statement structure; and
2. the official **Canadian Centre for Cyber Security ITSP.10.033** publications as the
   authoritative source for Canadian wording, assurance-activity classification, GC-specific
   discussion, 400-series additions, and the Medium-impact profile (ITSP.10.033-01).

The output is a high-integrity structured corpus intended for exact lookup, metadata filtering,
graph traversal, and (later, outside this repository) semantic retrieval and evidence assessment
-- not a black-box RAG index. See `specification.md` for the full design.

## Architecture

```text
NIST SP 800-53 Rev. 5 OSCAL
        |
        | structured baseline
        v
NIST normalized catalogue  (data/normalized/nist/)
        |
        +--------------+
        |              |
        v              v
ITSP.10.033 HTML   reconciliation
        |              |
        +------+-------+
               v
      Canadian catalogue  (data/normalized/reconciliation/catalogue.jsonl)
               |
               v
     ITSP.10.033-01 profile join
               |
               v
 JSONL / CSV / graph / derived-OSCAL / embedding-ready exports  (data/output/)
```

### Authority rules

1. **NIST OSCAL is authoritative for the machine-readable representation of NIST SP 800-53
   Rev. 5 content** -- the importer parses the official OSCAL Catalog JSON directly rather than
   reconstructing controls from prose.
2. **The Cyber Centre is authoritative for ITSP.10.033 and Canadian applicability/wording.** When
   the Cyber Centre restates a field, that Canadian text wins in the final dataset.
3. A same-named/same-ID record is **never** assumed identical between the two sources. Every
   final record carries an `origin` and `reconciliation_status` explaining whether content was
   inherited unchanged, modified by the Cyber Centre, reclassified as an assurance activity, or
   added only in Canada (400-series) -- see `canadian_delta` for the specific fields that differ
   and why.
4. Fuzzy title matching is diagnostic-only and never finalizes a NIST-to-Canada mapping; mapping
   is always done through the id hierarchy (`itsp_kb.ids`).

## Install

```bash
mise install   # pins Python 3.12 and uv (see mise.toml)
uv sync        # installs runtime + dev dependencies (see pyproject.toml)
```

## Quick start

```bash
uv run itsp-kb fetch                                  # snapshot NIST OSCAL + all ITSP.10.033/-01 pages
uv run itsp-kb build                                   # full deterministic pipeline -> data/output/
uv run itsp-kb show AC-02                              # inspect one final Canadian record + lineage
uv run itsp-kb show AC-02 --upstream                   # inspect the corresponding NIST OSCAL object
uv run itsp-kb render-embeddings --view requirement_only
uv run pytest                                          # offline, fixture-driven test suite
```

`itsp-kb build` runs `fetch -> import-nist -> parse-canada -> reconcile -> parse-profile medium ->
validate -> export -> render-embeddings -> manifest`. Add `--strict` to fail the build on any
unresolved mapping, schema violation, or detected content anomaly instead of just warning.

## Individual pipeline stages

```bash
uv run itsp-kb fetch [--offline] [--force-fetch] [--nist-ref <commit-or-tag>] [--publication <name>]
uv run itsp-kb import-nist [--allow-newer-oscal]
uv run itsp-kb parse-canada [--family AC]
uv run itsp-kb reconcile [--family AC]
uv run itsp-kb parse-profile medium
uv run itsp-kb import-profile-spreadsheet path/to/official.xlsx   # optional, spec S9
uv run itsp-kb validate [--json]
uv run itsp-kb export
uv run itsp-kb diff <old-data-root> <new-data-root>
```

Every command accepts `--output <path>` to point at an alternate `data/` root and `--strict` to
turn warnings into hard failures.

## Source/version pinning

`config/sources.yaml` is the source registry. The NIST OSCAL source's `source_ref: "main"` is a
mutable branch; every `fetch` resolves it to a concrete Git commit SHA via the GitHub API *before*
downloading, and that resolved commit -- plus the OSCAL `metadata.version`, `oscal-version`, and a
SHA-256 of the downloaded bytes -- is recorded in `data/raw/nist_sp800_53_rev5_oscal/<date>/fetch.json`
and carried through into every downstream record's `sources.nist` and into the build manifest. Pass
`--nist-ref <commit-or-tag>` to pin a production build to a specific commit instead of `main`.
Each ITSP.10.033 family page and the Medium-profile page get their own dated snapshot with the
same `fetch.json`/`sha256.txt` provenance under `data/raw/itsp_10_033/<date>/<family-slug>/` and
`data/raw/itsp_10_033_01/<date>/`.

`itsp-kb fetch --offline` (also the default for `itsp-kb build --offline`) never touches the
network and rebuilds entirely from whatever is already in `data/raw/`.

## Output files

```text
data/output/
├── upstream/nist/{metadata.json, families.json, records.jsonl, relationships.jsonl}
├── catalogue/{families.json, controls.jsonl, controls.csv, enhancements.jsonl, all_records.jsonl}
├── reconciliation/{records.jsonl, report.json, report.md}
├── profiles/{medium.json, medium.jsonl, medium.csv}
├── relationships/edges.jsonl
├── oscal/{ITSP_10_033_catalog.json, ITSP_10_033_01_medium_profile.json}
├── embeddings/{embedding_records.jsonl, embedding_records.csv}
└── manifests/{build.json, sources.json}
```

JSONL is the canonical interchange format; CSV is a convenience export only. The `oscal/` exports
are explicitly labeled non-official derived representations (see each file's `metadata.remarks`)
-- they are not a claim of an official Cyber Centre OSCAL publication.

## Record and reconciliation schema (abridged)

A final Canadian record (`data/normalized/reconciliation/catalogue.jsonl`, schema at
`src/itsp_kb/schemas/control.schema.json`):

```json
{
  "id": "AC-02",
  "family_id": "AC",
  "record_kind": "base",
  "requirement_kind": "control",
  "origin": "nist_modified_canada",
  "nist_oscal_id": "ac-2",
  "reconciliation_status": "verified_modified",
  "is_canadian_specific": false,
  "canadian_delta": { "statement_changed": true, "discussion_changed": true, "fields": ["statement_text", "discussion"] },
  "enhancement_ids": ["AC-02(01)", "..."],
  "profile_memberships": { "medium": true },
  "sources": { "nist": {"...": "..."}, "canada": {"...": "..."} }
}
```

The paired reconciliation record (`data/output/reconciliation/records.jsonl`, schema at
`src/itsp_kb/schemas/reconciliation.schema.json`) carries the field-by-field diff (`same` /
`formatting_only` / `modified` / `canada_only` / `nist_only` / `unresolved`) that produced the
`reconciliation_status` above, including the NIST and Canadian content hashes for each field.

## Embedding-ready representations

```bash
uv run itsp-kb render-embeddings --view requirement_only            # ID/name/type/origin + requirement + ODPs
uv run itsp-kb render-embeddings --view requirement_plus_discussion # + Discussion + GC discussion
uv run itsp-kb render-embeddings --view full                        # + related controls + Medium-profile info
uv run itsp-kb render-embeddings --view canada_delta                # focused on what's Canadian-specific/changed
```

No embedding model is invoked anywhere in this repository; these commands only produce
deterministic text + metadata records for an external embedding step to consume later.

## Diffing two builds

```bash
uv run itsp-kb build --output builds/2026-09-22
# ... time passes, sources change ...
uv run itsp-kb build --output builds/2026-10-01
uv run itsp-kb diff builds/2026-09-22 builds/2026-10-01
```

`diff` reports NIST/Canadian source-version changes, added/removed records, withdrawal and
reconciliation-status changes, and authoritative-text changes -- using the same comparison
normalizer as reconciliation, so a formatting-only difference (whitespace, NBSP, outline-marker
punctuation, or an ODP's bracket-vs-template rendering) is never reported as a content change.

## Known limitations (v1)

- **NIST ODP-count comparison is a heuristic.** `canadian_delta.parameters_changed` compares the
  count of OSCAL `*_odp.NN` params against extracted `[Assignment: ...]`/`[Selection: ...]`
  brackets; an OSCAL "aggregator" parameter can merge several `_odp.` ids into one rendered
  bracket, so this can overcount slightly relative to what a reader actually sees. It is a
  deterministic, reproducible signal for review, not a claim of exact correspondence.
- **Nested ODP brackets** (e.g. `[Selection (1): [Assignment: ...]; at random time intervals]]`,
  confirmed in SC-30(03)) are only partially decomposed by the bracket extractor, which assumes
  non-nested bodies; the raw statement text itself is always preserved verbatim regardless.
- **Two confirmed defects in the official Cyber Centre source itself** are surfaced (not silently
  fixed) by `itsp-kb validate`: an unclosed `[Assignment: ...]` bracket in enhancement MA-04(05),
  and a stray extra `]` in enhancement SC-30(03). See `docs/VERIFICATION.md`.
- **One confirmed defect in the official Medium-profile spreadsheet-equivalent table**: table 4.5
  has two different rows both labeled `CM-11(02)` (one should be `CM-11(03)` per the main
  catalogue's own numbering); `parse-profile` warns and keeps the first-seen row.
- Two controls (AC-12, PE-22) are rendered by the Cyber Centre with a literal `Activity/Control:`
  label rather than committing to one kind; these are left as `requirement_kind: unknown` rather
  than guessed.
- French-language sources, ITSP.10.035/.036/.037, and ITSP.10.033-02 are explicitly out of scope
  for v1 (spec S28); the data model's `publication` fields are left extensible for them.

## Repository layout

See `specification.md` S4 for the full canonical layout. Two intentional, documented deviations:
each ITSP.10.033 family page's raw snapshot lives in its own `data/raw/itsp_10_033/<date>/<slug>/`
subdirectory (rather than one flat file) so 20 pages fetched on the same day each get their own
`fetch.json`/`sha256.txt`; and the CSV exporter (`exporters/csv.py`) is a thin re-export of
`exporters/jsonl.py` so the JSONL and CSV catalogue exports are derived from one loaded copy of
the catalogue rather than two.

## Testing

```bash
uv run pytest        # fully offline; all fixtures are trimmed from real fetched snapshots
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src/itsp_kb
```

Fixtures under `tests/fixtures/` are not hand-written: they are trimmed excerpts of real NIST
OSCAL controls and real Cyber Centre HTML, captured while building this pipeline against the live
sources, specifically chosen to cover an inherited control, a modified control, an assurance-
activity reclassification, GC discussion, a 400-series Canada-only base record and enhancement, a
withdrawn record, and two unusual (but real) HTML classification renderings.
