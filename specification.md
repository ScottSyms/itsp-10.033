# Specification: ITSP.10.033 Structured Knowledge Base Extractor — NIST OSCAL Baseline + Canadian Overlay

**Working repository name:** `itsp-knowledge-base`  
**Primary implementation language:** Python 3.12+  
**Specification version:** 2.0  
**Source authorities:** Canadian Centre for Cyber Security for ITSP content; NIST for the SP 800-53 Rev. 5 OSCAL baseline  
**Primary outputs:** JSONL, JSON, CSV, manifest/provenance files, embedding-ready text records  
**Primary consumer:** AI/RAG/evidence-assessment systems

**Revision note:** Version 2.0 replaces the original HTML-first extraction design with a NIST OSCAL baseline → Canadian overlay → reconciliation architecture.

---

## 1. Objective

Build a deterministic, repeatable pipeline that produces a structured Canadian ITSP.10.033 knowledge base by combining:

1. the official **NIST SP 800-53 Rev. 5 OSCAL catalogue** as the pre-structured baseline for NIST-derived controls, enhancements, parameters, parts, links, and references; and
2. the official **Canadian Centre for Cyber Security ITSP.10.033** publications as the authoritative source for the Canadian implementation, including Canadian wording, assurance activities, GC-specific discussion, Canadian references, Canadian 400-series additions, and the Medium-impact profile.

The architecture MUST be:

```text
NIST SP 800-53 Rev. 5 OSCAL
        │
        │ structured baseline
        ▼
NIST normalized catalogue
        │
        ├──────────────┐
        │              │
        ▼              ▼
ITSP.10.033 HTML   reconciliation
        │              │
        └───────┬──────┘
                ▼
       Canadian catalogue
                │
                ▼
      ITSP.10.033-01 profile
                │
                ▼
 JSONL / CSV / graph / OSCAL-compatible export /
 embedding-ready representations
```

The pipeline MUST support:

1. exact control/activity lookup;
2. metadata filtering;
3. semantic/vector retrieval;
4. graph traversal between related controls and activities;
5. mapping the Medium-impact profile to the final Canadian catalogue;
6. explicit identification of Canadian deltas from NIST;
7. later assessment of security/privacy evidence against controls and assurance activities;
8. generation of embedding-ready representations without making an embedding model part of extraction.

The system MUST NOT treat NIST content as automatically identical to ITSP.10.033 merely because the identifiers align. The final Canadian record MUST have a reconciliation status and provenance showing whether content was inherited unchanged, modified by the Cyber Centre, converted/reclassified, or added only in Canada.

The initial implementation MUST fully support:

- **NIST SP 800-53 Rev. 5 OSCAL catalogue** — official JSON baseline from `usnistgov/oscal-content`.
- **ITSP.10.033** — Security and privacy controls and assurance activities catalogue.
- **ITSP.10.033-01** — Suggested organizational security and privacy control and activity profile — Medium impact.

The repository and schema MUST be designed so these publications can be added without a breaking redesign:

- **ITSP.10.035** — Cyber security and privacy risk management: A lifecycle approach — Overview.
- **ITSP.10.036** — Organizational cyber security and privacy risk management activities.
- **ITSP.10.037** — System lifecycle cyber security and privacy risk management activities.
- **ITSP.10.033-02** — Assessment of security and privacy controls and assurance activities.

## 2. Design principles

### 2.1 Baseline, overlay, reconciliation

Use NIST OSCAL to avoid reconstructing the NIST control model from HTML.

Use Cyber Centre material to construct the authoritative Canadian result.

The pipeline MUST distinguish:

```text
upstream baseline     = NIST OSCAL
Canadian overlay      = ITSP.10.033
final authority       = Cyber Centre for ITSP meaning/content
profile overlay       = ITSP.10.033-01
```

NIST data is an upstream structured source, not a substitute for validating ITSP content.

### 2.2 Deterministic extraction

Given the same source snapshots, the pipeline MUST produce semantically identical output.

Do not use generative AI for primary parsing, mapping, reconciliation, or profile joins.

AI may be added later as an optional enrichment stage, but generated fields MUST be clearly separated from authoritative extracted fields.

### 2.3 Preserve both upstream and Canadian source truth

Never rewrite official source wording during ingestion.

For a NIST-backed Canadian record, retain enough lineage to reproduce:

- the upstream OSCAL object and/or its canonical hash;
- the Canadian source text;
- the field-level differences;
- the selected final Canadian value;
- the reason/source for the selection.

Normalization MUST NOT overwrite authoritative text.

### 2.4 Stable identifiers

Use Cyber Centre identifiers as canonical Canadian IDs.

Examples:

- `AC-02`
- `AC-02(01)`
- `SA-400`
- `IA-04(400)`

Retain the original NIST OSCAL ID separately, for example:

```json
{
  "id": "AC-02(01)",
  "nist_oscal_id": "ac-2.1"
}
```

Do not renumber records. Withdrawn IDs, if present, MUST remain addressable.

### 2.5 Structure before embeddings

The knowledge base is not merely a collection of RAG chunks.

Structured fields MUST remain first-class so applications can perform filters, joins, provenance checks, and graph traversal before semantic search.

Example query flow:

```text
profile_medium = true
AND family IN ("AC", "IA")
AND reconciliation_status != "unresolved"
        ↓
semantic / lexical retrieval
        ↓
candidate controls
        ↓
evidence evaluation
```

### 2.6 Provenance everywhere

Every authoritative field MUST be traceable to NIST OSCAL, Cyber Centre content, or the Medium-profile publication.

Where a Canadian record differs from NIST, store the delta explicitly.

### 2.7 Idempotent rebuilds

Running the pipeline repeatedly against identical snapshots MUST not create duplicates or semantic changes.

Use canonical record IDs plus content hashes.

### 2.8 Fail loudly

A source-layout change, OSCAL schema/version incompatibility, ambiguous control mapping, or unresolved Canadian delta MUST cause validation failure in strict mode rather than silently emitting incomplete records.

### 2.9 Minimize duplicated extraction work

Do not re-parse from Canadian HTML any structure already reliably supplied by OSCAL unless the Canadian source differs or is needed for validation.

In particular, the NIST importer SHOULD provide the initial:

- family/group structure;
- control/enhancement hierarchy;
- parameter objects;
- statement part hierarchy;
- related links/references when present;
- upstream identifiers.

The Canadian extractor SHOULD focus on:

- Canadian text and modifications;
- `Control` versus `Activity` classification;
- GC discussion;
- Canadian references;
- Canadian-specific 400-series records;
- Canadian-specific enhancements;
- Canadian ODP changes;
- withdrawals/reclassifications;
- reconciliation/validation.

## 3. Official source set

Create a source registry rather than scattering URLs through parser code.

Initial registry entries:

```yaml
sources:
  nist_sp800_53_rev5_oscal:
    publication: "NIST SP 800-53 Rev. 5"
    title: "Security and Privacy Controls for Information Systems and Organizations"
    type: "oscal_catalog"
    authority: "NIST"
    format: "json"
    repository: "https://github.com/usnistgov/oscal-content"
    path: "nist.gov/SP800-53/rev5/json/NIST_SP-800-53_rev5_catalog.json"
    raw_url: "https://raw.githubusercontent.com/usnistgov/oscal-content/main/nist.gov/SP800-53/rev5/json/NIST_SP-800-53_rev5_catalog.json"
    source_ref: "main"       # resolve and record commit SHA during fetch
    language: "en"

  itsp_10_033:
    publication: "ITSP.10.033"
    title: "Security and privacy controls and assurance activities catalogue"
    root_url: "https://www.cyber.gc.ca/en/guidance/cyber-security-privacy-risk-management/itsp10033"
    type: "canadian_catalogue_overlay"
    authority: "Canadian Centre for Cyber Security"
    language: "en"

  itsp_10_033_01:
    publication: "ITSP.10.033-01"
    title: "Suggested organizational security and privacy control and activity profile — Medium impact"
    root_url: "https://www.cyber.gc.ca/en/guidance/cyber-security-privacy-risk-management/suggested-organizational-security-privacy-control-activity-profile-medium-impact-itsp10033-01"
    type: "profile"
    authority: "Canadian Centre for Cyber Security"
    language: "en"

  itsp_10_036:
    publication: "ITSP.10.036"
    title: "Organizational cyber security and privacy risk management activities"
    root_url: "https://www.cyber.gc.ca/en/guidance/cyber-security-privacy-risk-management/organizational-cyber-security-privacy-risk-management-activities-itsp10036"
    type: "lifecycle"
    authority: "Canadian Centre for Cyber Security"
    language: "en"
    enabled: false
```

The source registry MUST support adding French-language equivalents later.

### 3.1 Authority rules

Apply these authority rules:

1. **NIST OSCAL is authoritative for the machine-readable representation of NIST SP 800-53 Rev. 5 content.**
2. **The Cyber Centre is authoritative for ITSP.10.033 and Canadian applicability/wording.**
3. If the Cyber Centre supplies text for a mapped record, that Canadian text wins in the final ITSP dataset.
4. If a field is not restated by the Cyber Centre and deterministic validation establishes inheritance, the final dataset MAY reference the upstream NIST value rather than duplicate it.
5. Never infer that a field is inherited merely because a control ID exists in both sources.

### 3.2 Acquisition preference

Use source formats in this order:

For the NIST baseline:

1. official NIST OSCAL JSON from the `usnistgov/oscal-content` repository;
2. official NIST OSCAL XML/YAML only as validation/fallback;
3. NIST publication text only for manual verification.

For Canadian content:

1. official Cyber Centre HTML;
2. official machine-readable spreadsheet, if obtained directly from the Cyber Centre;
3. official Cyber Centre PDF as validation/fallback.

Do not scrape search-engine caches or third-party copies.

### 3.3 Version pinning

The NIST repository's `main` branch is mutable. A reproducible build MUST record:

```text
repository URL
configured source_ref
resolved Git commit SHA
OSCAL metadata.version
OSCAL metadata.oscal-version
source SHA-256
retrieval timestamp
```

After the initial fetch, release/production builds SHOULD pin the NIST source to a commit SHA rather than implicitly consuming whatever is on `main`.

A change in NIST `metadata.version`, `oscal-version`, or resolved commit MUST appear in the build diff.

### 3.4 Source snapshotting

For reproducibility, save fetched source material under:

```text
data/raw/<source-id>/<retrieval-date>/
```

Examples:

```text
data/raw/nist_sp800_53_rev5_oscal/2026-09-22/catalog.json
data/raw/itsp_10_033/2026-09-22/source.html
```

At minimum save:

```text
source content
headers.json where applicable
fetch.json
sha256.txt
```

Where applicable also save PDFs/spreadsheets.

`fetch.json` example:

```json
{
  "source_id": "nist_sp800_53_rev5_oscal",
  "publication": "NIST SP 800-53 Rev. 5",
  "url": "https://raw.githubusercontent.com/.../NIST_SP-800-53_rev5_catalog.json",
  "configured_ref": "main",
  "resolved_commit": "<git-sha>",
  "retrieved_at": "2026-09-22T15:00:00Z",
  "http_status": 200,
  "content_type": "application/json",
  "sha256": "..."
}
```

Use conditional GETs where supported. Rate-limit requests and identify the client with a descriptive User-Agent.

## 4. Canonical repository layout

Implement this layout unless a clearly superior equivalent is justified in `ARCHITECTURE.md`.

```text
itsp-knowledge-base/
├── README.md
├── SPEC.md
├── pyproject.toml
├── uv.lock
├── src/
│   └── itsp_kb/
│       ├── __init__.py
│       ├── cli.py
│       ├── config.py
│       ├── fetch.py
│       ├── normalize.py
│       ├── validate.py
│       ├── provenance.py
│       ├── reconcile.py
│       ├── ids.py
│       ├── models/
│       │   ├── common.py
│       │   ├── nist.py
│       │   ├── catalogue.py
│       │   ├── reconciliation.py
│       │   ├── profile.py
│       │   └── lifecycle.py
│       ├── parsers/
│       │   ├── base.py
│       │   ├── nist_oscal.py
│       │   ├── itsp_10_033.py
│       │   ├── itsp_10_033_01.py
│       │   └── html_utils.py
│       ├── exporters/
│       │   ├── jsonl.py
│       │   ├── csv.py
│       │   ├── graph.py
│       │   ├── oscal.py
│       │   └── embeddings.py
│       └── schemas/
│           ├── nist_record.schema.json
│           ├── control.schema.json
│           ├── reconciliation.schema.json
│           ├── profile.schema.json
│           └── embedding.schema.json
├── config/
│   └── sources.yaml
├── data/
│   ├── raw/
│   │   ├── nist_sp800_53_rev5_oscal/
│   │   ├── itsp_10_033/
│   │   └── itsp_10_033_01/
│   ├── normalized/
│   │   ├── nist/
│   │   ├── canada/
│   │   └── reconciliation/
│   └── output/
│       ├── upstream/
│       ├── catalogue/
│       ├── reconciliation/
│       ├── profiles/
│       ├── relationships/
│       ├── oscal/
│       ├── embeddings/
│       └── manifests/
├── tests/
│   ├── fixtures/
│   │   ├── nist_oscal/
│   │   └── cyber_centre/
│   ├── test_ids.py
│   ├── test_nist_oscal.py
│   ├── test_reconciliation.py
│   ├── test_odp.py
│   ├── test_catalogue_parser.py
│   ├── test_profile_parser.py
│   ├── test_relationships.py
│   ├── test_validation.py
│   └── test_snapshots.py
└── scripts/
    └── inspect_source.py
```

## 5. Domain model

Use typed models, preferably Pydantic v2.

The final authoritative unit is a **Canadian control/activity record**. Enhancements MUST also be independently addressable records while preserving their parent relationship.

The pipeline additionally maintains a normalized **NIST upstream record** and a **reconciliation record**.

### 5.1 Family

```json
{
  "id": "AC",
  "name": "Access control",
  "publication": "ITSP.10.033",
  "nist_group_id": "ac",
  "source_url": "...",
  "source_hash": "..."
}
```

The catalogue currently organizes records into these 20 families:

```text
AC  Access control
AT  Awareness and training
AU  Audit and accountability
CA  Assessment, authorization, and monitoring
CM  Configuration management
CP  Contingency planning
IA  Identification and authentication
IR  Incident response
MA  Maintenance
MP  Media protection
PE  Physical and environmental protection
PL  Planning
PM  Program management
PS  Personnel security
PT  Personal information handling and transparency
RA  Risk assessment
SA  System and services acquisition
SC  System and communications protection
SI  System and information integrity
SR  Supply chain risk management
```

The pipeline MUST validate these against both the NIST OSCAL group set and the Cyber Centre source. Differences MUST be reported.

### 5.2 NIST upstream record

Normalize OSCAL into an internal form without discarding OSCAL-native identifiers or part structure.

```json
{
  "upstream_id": "ac-2",
  "canonical_candidate_id": "AC-02",
  "family_id": "AC",
  "title": "Account Management",
  "oscal_uuid": null,
  "props": [],
  "params": [],
  "parts": [],
  "child_control_ids": ["ac-2.1"],
  "links": [],
  "source": {
    "publication": "NIST SP 800-53 Rev. 5",
    "metadata_version": "...",
    "oscal_version": "...",
    "git_commit": "...",
    "source_sha256": "..."
  }
}
```

Retain unknown OSCAL properties/parts in an `extensions` or `unmapped` field rather than discarding them.

### 5.3 Canadian base control/activity record

Canonical JSON model:

```json
{
  "schema_version": "2.0",
  "id": "AC-02",
  "family_id": "AC",
  "family_name": "Access control",
  "number": "02",
  "name": "Account management",

  "record_kind": "base",
  "requirement_kind": "control",

  "origin": "nist_inherited",
  "nist_oscal_id": "ac-2",
  "reconciliation_status": "verified_inherited",
  "is_canadian_specific": false,
  "is_withdrawn": false,

  "statements": [
    {
      "path": "a",
      "text": "Define and document ...",
      "children": []
    }
  ],

  "statement_text": "Flattened authoritative Canadian statement text",
  "discussion": "General Canadian/ITSP discussion, if present",
  "gc_discussion": "Government of Canada discussion, if present",

  "odps": [],
  "related": [],
  "references": [],
  "enhancement_ids": ["AC-02(01)"],

  "canadian_delta": {
    "title_changed": false,
    "statement_changed": false,
    "discussion_changed": false,
    "parameters_changed": false,
    "related_changed": false,
    "references_changed": false,
    "requirement_kind_changed": false,
    "fields": []
  },

  "profile_memberships": {},

  "sources": {
    "nist": {
      "publication": "NIST SP 800-53 Rev. 5",
      "oscal_id": "ac-2",
      "source_sha256": "...",
      "git_commit": "..."
    },
    "canada": {
      "publication": "ITSP.10.033",
      "url": "...",
      "section": "Access control > AC-02 Account management",
      "retrieved_at": "...",
      "source_sha256": "..."
    }
  }
}
```

### 5.4 Origin and reconciliation status

Use controlled values.

`origin`:

```text
nist_inherited
nist_modified_canada
nist_reclassified_activity
canada_only
unknown
```

`reconciliation_status`:

```text
verified_inherited
verified_modified
verified_reclassified
verified_canada_only
unresolved
```

Definitions:

- `verified_inherited`: mapped to NIST and all authoritative fields used by the final record have been verified equivalent or explicitly inherited.
- `verified_modified`: same conceptual NIST control/enhancement exists, but one or more Canadian authoritative fields differ.
- `verified_reclassified`: a NIST-aligned item is represented as an assurance activity or otherwise changes requirement kind in ITSP.
- `verified_canada_only`: no NIST record exists; typically a Canadian 400-series addition.
- `unresolved`: deterministic mapping/reconciliation is incomplete. Strict builds MUST fail on unresolved active records.

### 5.5 Enhancement record

An enhancement MUST be emitted as an independently searchable record.

```json
{
  "schema_version": "2.0",
  "id": "AC-02(01)",
  "parent_id": "AC-02",
  "family_id": "AC",
  "name": "Account management: Automated system account management",
  "record_kind": "enhancement",
  "requirement_kind": "control",
  "enhancement_number": "01",
  "origin": "nist_inherited",
  "nist_oscal_id": "ac-2.1",
  "reconciliation_status": "verified_inherited",
  "is_canadian_specific": false,
  "statements": [],
  "statement_text": "...",
  "discussion": "...",
  "gc_discussion": null,
  "odps": [],
  "related": [],
  "references": [],
  "sources": {}
}
```

Requirements:

- `parent_id` MUST resolve to a base record.
- An enhancement MUST inherit family metadata.
- NIST nested child-control relationships MUST map deterministically to Canadian enhancement notation.
- ODPs in the base MUST NOT be silently copied into enhancement text; inherited applicability MUST be represented explicitly if useful.

### 5.6 Canonical ID mapping

Implement one tested ID mapper between OSCAL IDs and Canadian canonical IDs.

Examples:

```text
ac-1      -> AC-01
ac-2      -> AC-02
ac-2.1    -> AC-02(01)
sa-8.33   -> SA-08(33)
```

The mapper MUST use the OSCAL parent/child hierarchy where available rather than relying only on string splitting.

Retain the original OSCAL ID in all cases.

Do not map Canadian 400-series IDs to NIST unless an explicit source-backed mapping exists.

### 5.7 Canadian-specific records

The Cyber Centre states that Canadian-specific controls, activities, or enhancements begin at 400.

Set:

```json
{
  "origin": "canada_only",
  "reconciliation_status": "verified_canada_only",
  "is_canadian_specific": true,
  "nist_oscal_id": null
}
```

for examples such as:

```text
SA-400
IA-04(400)
```

Preserve Canada-specific statement designators where the source uses them.

### 5.8 Requirement kind

The catalogue distinguishes controls from assurance activities.

Use:

```text
control
activity
unknown
```

Populate this from the Cyber Centre source. NIST does not get to override the Canadian classification.

### 5.9 Statement hierarchy

Preserve hierarchy in both upstream and final records.

Recommended Canadian node:

```json
{
  "path": "a.1",
  "source_designator": "A.1",
  "text": "...",
  "children": []
}
```

Also provide deterministic flattened `statement_text`.

Where feasible, preserve the corresponding NIST OSCAL `part.id` or path to support field-level reconciliation.

### 5.10 Organization-defined parameters (ODPs)

ODPs MUST be first-class objects.

For NIST-backed records, import OSCAL `param` objects first and then reconcile them with Cyber Centre bracketed placeholders.

Canadian ODP model:

```json
{
  "odp_id": "AC-02:odp:001",
  "nist_param_id": "ac-02_odp.01",
  "operation": "assignment",
  "cardinality": null,
  "raw": "[Assignment: organization-defined ...]",
  "prompt": "organization-defined ...",
  "options": [],
  "statement_path": "c",
  "character_start": 123,
  "character_end": 181
}
```

Recognize at least:

```text
[Assignment: ...]
[Selection: ...]
[Selection (one or more): ...]
[Selection (1 or more): ...]
```

Every ODP MUST retain its Canadian raw text where present.

A parameter mismatch between NIST OSCAL and ITSP MUST be represented in `canadian_delta.parameters_changed` and reported by reconciliation.

### 5.11 References and links

Store NIST links/back-matter references and Canadian references independently before reconciliation.

Final references MAY contain source lineage:

```json
{
  "title": "Directive on Security Management",
  "url": "https://...",
  "publisher": "Treasury Board of Canada Secretariat",
  "external": true,
  "source_authority": "Canada"
}
```

### 5.12 Withdrawn content

If a record is marked withdrawn by either source, preserve it and record the status by source.

Do not delete or reuse withdrawn identifiers.

## 6. NIST SP 800-53 Rev. 5 OSCAL importer

### 6.1 Purpose

The NIST importer is the structured seed for all NIST-derived ITSP records.

It MUST parse the official OSCAL Catalog JSON rather than reconstructing NIST controls from PDF/HTML.

### 6.2 OSCAL structures to support

At minimum support these OSCAL Catalog concepts:

```text
catalog
metadata
groups
controls
nested controls/enhancements
params
parts
props
links
back-matter/resources
```

OSCAL groups are the initial source for families. Nested `control` objects are the initial source for enhancement relationships. `param` objects are the initial source for organization-defined parameters. `part` objects are the initial source for statement/discussion/objective-like structure.

Do not assume every useful part has a fixed name beyond known NIST conventions. Preserve unknown parts.

### 6.3 Metadata capture

Capture at least:

```text
metadata.title
metadata.last-modified
metadata.version
metadata.oscal-version
catalog.uuid if present
resolved repository commit
source SHA-256
```

Fail validation if the OSCAL version is newer than the highest version the parser declares compatibility with, unless `--allow-newer-oscal` is explicitly supplied.

### 6.4 Group/family import

For each OSCAL group:

- preserve `id`, `class`, `title`, `props`, and links;
- map recognized NIST control-family groups to uppercase two-character family IDs;
- retain all other groups rather than discarding them;
- validate the expected SP 800-53 family set against the Cyber Centre family set later.

### 6.5 Control and enhancement import

For each OSCAL `control`:

1. retain original `control.id`;
2. retain title;
3. retain props;
4. retain params;
5. recursively retain parts;
6. retain links;
7. recursively process nested controls;
8. record parent/child relationships;
9. generate a Canadian canonical candidate ID using the tested mapper.

Do not flatten enhancements into their parent.

### 6.6 Parameter import

Represent each OSCAL `param` with at least:

```json
{
  "id": "...",
  "label": "...",
  "description": "...",
  "values": [],
  "select": null,
  "constraints": [],
  "guidelines": [],
  "props": [],
  "links": []
}
```

Preserve raw OSCAL structure if fields cannot be represented losslessly.

### 6.7 Part import

Recursively preserve OSCAL parts.

Internal normalized node:

```json
{
  "id": "...",
  "name": "statement",
  "prose": "...",
  "props": [],
  "links": [],
  "parts": []
}
```

Provide helper functions for known semantic views such as:

```text
statement_parts
assessment_objective_parts
guidance_parts
```

but do not delete unrecognized part names.

### 6.8 Back-matter/reference resolution

Resolve local fragment links into OSCAL back-matter resources when possible.

Retain both:

- original link `href`;
- resolved resource metadata/rlinks.

Unresolved local references MUST be warnings or errors according to strictness settings.

### 6.9 Normalized upstream output

Emit:

```text
data/normalized/nist/families.json
data/normalized/nist/records.jsonl
data/normalized/nist/relationships.jsonl
data/normalized/nist/metadata.json
```

This normalized dataset is an intermediate artifact. It is NOT the final ITSP catalogue.

### 6.10 OSCAL round-trip safety

The importer does not need byte-for-byte round-trip serialization, but it MUST retain enough information to avoid silently dropping control semantics.

Any unsupported OSCAL content MUST be preserved under an explicit `unmapped`/`extensions` field and counted in validation output.

## 7. ITSP.10.033 Canadian overlay parser and reconciliation

### 7.1 Purpose

The Cyber Centre parser is no longer responsible for inventing the entire NIST-derived data model from HTML. It extracts the Canadian representation and reconciles it against the structured NIST baseline.

The Cyber Centre source remains authoritative for the final ITSP dataset.

### 7.2 Parsing strategy

The Cyber Centre catalogue is organized as a root publication and family pages.

The parser SHOULD:

1. fetch the root/table-of-contents page;
2. discover all family links;
3. fetch each family page;
4. identify Canadian record boundaries and IDs;
5. extract Canadian authoritative text/labels and Canada-specific sections;
6. map each non-400 record to the normalized NIST baseline where possible;
7. extract 400-series records as Canada-only records;
8. reconcile field by field;
9. emit final Canadian records plus reconciliation records.

Prefer semantic headings and DOM traversal over fragile CSS selectors.

### 7.3 What to reuse from NIST

For a mapped record, the NIST object SHOULD provide the initial structural expectation for:

```text
family
base/enhancement hierarchy
candidate title
statement hierarchy
parameter objects
known related/reference structures
```

The Canadian parser MUST still verify the Canadian source and extract fields needed to determine whether the NIST content is inherited or changed.

Do not copy a NIST value into the final Canadian record without a deterministic inheritance decision.

### 7.4 Canadian sections to extract explicitly

At minimum identify:

```text
Control / Activity classification
Canadian statement text when present
Discussion
GC discussion
Related controls and activities
Enhancements
References
ODPs/placeholders
withdrawn/replacement notes
```

Canadian 400-series records and enhancements MUST be parsed in full because they have no NIST baseline.

### 7.5 ID patterns

Support at least:

```regex
^[A-Z]{2}-\d{2,3}$
^[A-Z]{2}-\d{2,3}\(\d{2,3}\)$
```

Do not assume all identifiers are two digits forever.

### 7.6 Mapping rules

For each Canadian non-400 ID:

1. map Canadian canonical ID to candidate NIST OSCAL ID;
2. verify family and parent relationship;
3. verify title similarity after safe normalization;
4. compare statement structure/text;
5. compare parameters/ODPs;
6. compare discussion/guidance where semantically equivalent fields exist;
7. compare related controls/references where available;
8. capture Canadian-only sections such as GC discussion;
9. classify reconciliation status.

Never map solely on fuzzy title similarity when an ID mapping exists.

A fuzzy mapper MAY be used only as a diagnostic for an otherwise unresolved record and MUST NOT silently finalize the mapping.

### 7.7 Field-level comparison

For mapped records create a reconciliation object:

```json
{
  "canadian_id": "AC-02",
  "nist_oscal_id": "ac-2",
  "status": "verified_modified",
  "field_diffs": [
    {
      "field": "statement_text",
      "kind": "modified",
      "nist_hash": "...",
      "canada_hash": "...",
      "normalization_equal": false
    }
  ],
  "canada_only_fields": ["gc_discussion"],
  "nist_only_fields": [],
  "review_required": false
}
```

At minimum classify differences as:

```text
same
formatting_only
modified
canada_only
nist_only
unresolved
```

### 7.8 Safe comparison normalization

Comparison normalization MAY:

- normalize Unicode whitespace;
- collapse repeated whitespace;
- normalize list-marker formatting where semantics are unchanged;
- normalize non-breaking spaces;
- normalize Canadian/NIST ID display formatting solely for comparison.

It MUST NOT:

- paraphrase;
- remove normative modal verbs;
- discard bracketed parameters;
- reorder clauses;
- remove list numbering that carries meaning.

Store hashes of both raw/minimally-normalized and comparison-normalized forms.

### 7.9 Final-value rules

For final Canadian records:

- Canadian text wins whenever the Cyber Centre explicitly supplies the field.
- GC discussion is always Canadian-only.
- Canadian `Control`/`Activity` classification wins.
- Canada-only 400-series content comes exclusively from the Cyber Centre.
- If a Canadian page explicitly indicates inheritance/reference rather than restating content, the NIST value MAY be referenced as inherited with provenance.
- If inheritance cannot be proven deterministically, set `reconciliation_status = unresolved` and fail strict validation.

### 7.10 Assurance activity reclassification

The Cyber Centre explicitly treats assurance-related items as activities rather than controls.

When a mapped NIST item changes kind:

```json
{
  "origin": "nist_reclassified_activity",
  "reconciliation_status": "verified_reclassified",
  "requirement_kind": "activity",
  "canadian_delta": {
    "requirement_kind_changed": true
  }
}
```

Do not remove the NIST lineage.

### 7.11 Canadian 400-series additions

For every Canadian-specific base record/enhancement:

- parse the complete Canadian record;
- set `nist_oscal_id = null`;
- set `origin = canada_only`;
- set `reconciliation_status = verified_canada_only`;
- validate parent/family relationships;
- include it in all final catalogue, graph, profile, and embedding exports.

### 7.12 Related-control edges

For every final `related` identifier emit:

```json
{
  "source_id": "AC-02",
  "relationship": "related_to",
  "target_id": "IA-02",
  "source_publication": "ITSP.10.033",
  "lineage": "canada"
}
```

Also emit `enhancement_of` and `has_enhancement` edges.

NIST-only upstream edges MAY be emitted in a separate upstream graph but MUST NOT be silently treated as ITSP relationships unless reconciled.

### 7.13 Reconciliation validation

After parsing all families:

- every active Canadian non-400 record SHOULD map to exactly one NIST record unless explicitly documented otherwise;
- every Canada-only 400-series record MUST be recognized as such;
- every `parent_id` MUST resolve;
- every internal related-control ID SHOULD resolve;
- duplicate Canadian IDs MUST fail;
- duplicate upstream-to-Canadian mappings MUST fail unless explicitly modeled;
- unresolved mappings MUST fail strict builds;
- all field-level deltas MUST be reproducible from stored source data.

### 7.14 Reconciliation report

Generate human-readable and machine-readable reports:

```text
data/output/reconciliation/report.md
data/output/reconciliation/report.json
data/output/reconciliation/records.jsonl
```

The report MUST summarize:

```text
verified inherited records
verified modified records
reclassified activities
Canada-only records
unresolved records
field-level change counts
unmapped OSCAL structures
```

## 8. ITSP.10.033-01 Medium-impact profile parser

### 8.1 Source format

The public HTML profile contains one table per family with these conceptual columns:

```text
Family
ID
Name
Description
Control/Activity
Suggested for this profile
Suggested placeholder values
Profile-specific notes
```

Parse the tables directly or use the official Cyber Centre spreadsheet if supplied.

Do not infer profile selection from NIST baselines or the master catalogue.

### 8.2 Canonical profile record

Emit one profile entry per base control/activity row and, where represented, enhancement selections associated with it.

```json
{
  "profile_id": "medium",
  "profile_publication": "ITSP.10.033-01",
  "control_id": "AC-01",
  "family_id": "AC",
  "name": "Access control policy and procedures",
  "requirement_kind": "activity",
  "selected": true,
  "suggested_enhancements": [],
  "suggested_placeholder_values_raw": "...",
  "profile_specific_notes": null,
  "source": {
    "table": "Table 4.1: Access control",
    "url": "...",
    "retrieved_at": "...",
    "source_sha256": "..."
  }
}
```

Normalize source values deterministically and preserve the raw cell text in parallel fields.

### 8.3 Join to final Canadian catalogue

Join profile rows to **reconciled Canadian records**, not directly to NIST records.

Examples:

```text
AC + 01 -> AC-01
SA + 400 -> SA-400
```

Enhancement selections MUST resolve to full Canadian enhancement IDs.

The build MUST fail if:

- a selected profile record cannot be resolved to the Canadian catalogue;
- a suggested enhancement cannot be resolved to its parent;
- family and ID disagree;
- duplicate profile rows conflict;
- the target Canadian record has `reconciliation_status = unresolved` in strict mode.

### 8.4 Profile membership projection

After successful join, add profile membership to final Canadian exports while keeping the standalone profile dataset.

### 8.5 Optional OSCAL Profile export

Generate an optional OSCAL-compatible profile representation where semantics can be represented faithfully:

```text
data/output/oscal/ITSP_10_033_01_medium_profile.json
```

Use OSCAL `include-controls` for selected controls/enhancements and parameter alterations where appropriate.

Canadian assurance activities or profile semantics that do not map cleanly to OSCAL MUST be represented using documented namespaced extension properties rather than silently coerced.

The OSCAL-compatible export is derived. The canonical source of truth remains the internal Canadian JSONL/profile model plus provenance.

### 8.6 Medium-profile metadata

Store source-backed profile-level metadata including effective date, superseded profile, impact values, and robustness/assurance guidance where present.

## 9. Optional spreadsheet importer

The Cyber Centre states that a spreadsheet version of the Medium profile can be requested.

Design an optional importer:

```text
itsp-kb import-profile-spreadsheet path/to/file.xlsx
```

Requirements:

- spreadsheet import MUST use the same canonical profile model;
- HTML remains supported;
- importer MUST compare spreadsheet IDs against catalogue IDs;
- source type must be recorded as `official_spreadsheet`;
- differences between spreadsheet and HTML MUST be reported, not silently resolved.

Do not make availability of the spreadsheet a prerequisite for v1.

---

## 10. Future lifecycle and assessment documents

Do not implement these at the expense of the core v1 extractor, but make the data model extensible.

### 9.1 ITSP.10.036

Represent organizational risk-management activities as:

```json
{
  "id": "ITSP.10.036:<stable-section-id>",
  "publication": "ITSP.10.036",
  "kind": "organizational_activity",
  "phase": "...",
  "title": "...",
  "text": "...",
  "related_control_ids": [],
  "source": {}
}
```

### 9.2 ITSP.10.037

Represent system-lifecycle activities, assurance levels, engineering tasks, expected evidence, and lifecycle stages.

Suggested fields:

```text
lifecycle_phase
activity
role
input
output
evidence_artifact
sal
related_controls
```

### 9.3 ITSP.10.033-02

This should eventually become the assessment/evidence layer.

Design for records like:

```json
{
  "assessment_id": "...",
  "control_id": "AC-02",
  "objective": "...",
  "methods": ["examine", "interview", "test"],
  "objects": [],
  "expected_evidence": [],
  "source": {}
}
```

Do not fabricate assessment procedures if the publication is unavailable from the source registry. An unavailable source must remain explicitly unavailable.

---

## 11. Output datasets

The build command MUST generate:

```text
data/output/
├── upstream/
│   └── nist/
│       ├── metadata.json
│       ├── families.json
│       ├── records.jsonl
│       └── relationships.jsonl
├── catalogue/
│   ├── families.json
│   ├── controls.jsonl
│   ├── controls.csv
│   ├── enhancements.jsonl
│   └── all_records.jsonl
├── reconciliation/
│   ├── records.jsonl
│   ├── report.json
│   └── report.md
├── profiles/
│   ├── medium.json
│   ├── medium.jsonl
│   └── medium.csv
├── relationships/
│   └── edges.jsonl
├── oscal/
│   ├── ITSP_10_033_catalog.json
│   └── ITSP_10_033_01_medium_profile.json
├── embeddings/
│   ├── embedding_records.jsonl
│   └── embedding_records.csv
└── manifests/
    ├── build.json
    └── sources.json
```

### 11.1 JSONL

JSONL is the canonical bulk interchange format for the simplified Canadian knowledge-base representation.

One object per line, UTF-8, no comments.

### 11.2 CSV

CSV is a convenience export. Nested structures may be JSON-encoded or deterministically flattened.

CSV MUST NOT be the canonical source of truth.

### 11.3 OSCAL-compatible Canadian export

Generate a derived OSCAL Catalog JSON representing the reconciled Canadian catalogue.

Requirements:

- preserve Canadian canonical IDs using labels/properties where OSCAL native IDs require a different form;
- include controls/enhancements and parameter objects where faithfully representable;
- preserve assurance-activity distinction using documented extension properties/classes;
- include Canadian provenance metadata;
- include Canada-only 400-series records;
- do not claim the output is an official Cyber Centre OSCAL publication;
- validate against the supported OSCAL schema wherever possible.

### 11.4 Graph edges

`edges.jsonl` SHOULD distinguish Canadian-authoritative edges from upstream-only NIST edges and derived/inferred edges.

## 12. Embedding-ready representations

### 12.1 Separation from extraction

The extractor MUST NOT require an embedding provider.

It MUST produce deterministic embedding-ready text records from the **final reconciled Canadian catalogue**.

Do not embed upstream NIST records as though they were Canadian requirements. Upstream NIST representations MAY be exported separately for research/comparison.

### 12.2 One embedding record per semantic unit

Default units:

- one Canadian base control/activity;
- one Canadian enhancement;
- optionally one discussion-only representation;
- later one lifecycle activity or assessment procedure.

Do not create arbitrary fixed-token chunks that split a requirement in the middle.

### 12.3 Embedding record schema

```json
{
  "embedding_id": "ITSP.10.033:AC-02",
  "record_id": "AC-02",
  "record_kind": "base",
  "family_id": "AC",
  "family_name": "Access control",
  "name": "Account management",
  "requirement_kind": "control",
  "origin": "nist_modified_canada",
  "reconciliation_status": "verified_modified",
  "profile_medium": true,
  "is_canadian_specific": false,
  "text": "...",
  "source_publication": "ITSP.10.033",
  "source_url": "...",
  "canadian_source_hash": "...",
  "nist_source_hash": "..."
}
```

### 12.4 Embedding text template

Use Canadian authoritative text for requirement/discussion fields.

Recommended default:

```text
ID: {id}
Family: {family_name}
Name: {name}
Type: {requirement_kind}
Origin: {origin}
Canadian-specific: {yes/no}

Requirement:
{statement_text}

Organization-defined parameters:
{rendered_odps}

Discussion:
{discussion}

Government of Canada discussion:
{gc_discussion}

Related controls and activities:
{related_ids}

Medium-impact profile:
Selected: {yes/no}
Suggested enhancements: {enhancement_ids}
Suggested placeholder values: {values}
Profile-specific notes: {notes}
```

Do not include raw NIST text in the default Canadian embedding unless an explicit comparison view is requested.

### 12.5 Multiple embedding views

Support at minimum:

```text
requirement_only
requirement_plus_discussion
full
canada_delta
```

`canada_delta` is useful for retrieving controls by Canadian-specific differences and SHOULD include GC discussion, Canada-only modifications, and 400-series additions without flooding the text with unchanged upstream content.

### 12.6 Future actual-vector command

Keep actual embedding generation plugin/provider based and optional.

## 13. Retrieval-oriented metadata

Every embedding record SHOULD contain filterable metadata:

```text
id
family_id
record_kind
requirement_kind
profile_medium
is_canadian_specific
is_withdrawn
has_odp
has_gc_discussion
publication
effective_date
```

Recommended downstream retrieval sequence:

1. metadata filter;
2. lexical/BM25 and/or vector retrieval;
3. optional reranking;
4. evidence evaluation.

The repository does not need to implement a vector database in v1.

---

## 14. Source provenance and change detection

### 14.1 Build manifest

Generate a build manifest containing both source authorities.

```json
{
  "build_id": "2026-09-22T15:00:00Z",
  "schema_version": "2.0",
  "extractor_version": "0.2.0",
  "sources": {
    "nist": {
      "metadata_version": "...",
      "oscal_version": "...",
      "git_commit": "...",
      "source_sha256": "..."
    },
    "itsp_10_033": {
      "source_sha256": "..."
    },
    "itsp_10_033_01": {
      "source_sha256": "..."
    }
  },
  "record_counts": {
    "nist_records": 0,
    "canadian_base_records": 0,
    "canadian_enhancements": 0,
    "verified_inherited": 0,
    "verified_modified": 0,
    "verified_reclassified": 0,
    "verified_canada_only": 0,
    "unresolved": 0,
    "profile_rows": 0,
    "edges": 0
  },
  "validation": {
    "passed": true,
    "warnings": []
  }
}
```

Counts are calculated, never hard-coded.

### 14.2 Per-record hashes

Maintain separate hashes for:

```text
NIST upstream authoritative content
Canadian authoritative content
comparison-normalized content
final reconciled record
```

This makes it possible to distinguish an upstream NIST revision from a Canadian revision and from a parser change.

### 14.3 Diff command

`itsp-kb diff old-build/ new-build/` MUST report at least:

```text
NIST upstream version/commit changes
Canadian source changes
added/removed/withdrawn Canadian records
changed authoritative Canadian text
changed NIST-to-Canada reconciliation status
changed ODPs
changed relationships
changed profile selection
changed profile parameter values
changed source metadata
```

Formatting-only normalization differences MUST not be classified as authoritative content changes.

## 15. CLI

Provide a CLI named `itsp-kb`.

Required commands:

```bash
# Fetch all configured sources, including NIST OSCAL and Cyber Centre pages
itsp-kb fetch

# Import/normalize the NIST OSCAL baseline
itsp-kb import-nist

# Parse Canadian source snapshots
itsp-kb parse-canada

# Reconcile NIST baseline against ITSP.10.033
itsp-kb reconcile

# Parse/join the Medium profile
itsp-kb parse-profile medium

# Validate all layers
itsp-kb validate

# Export JSONL/CSV/graph/derived OSCAL
itsp-kb export

# Complete deterministic pipeline
itsp-kb build

# Compare builds
itsp-kb diff <old> <new>

# Inspect one final Canadian record plus lineage
itsp-kb show AC-02

# Inspect the corresponding NIST upstream object
itsp-kb show AC-02 --upstream

# Produce embedding-ready representations
itsp-kb render-embeddings --view requirement_only
```

Useful options:

```text
--publication ITSP.10.033
--family AC
--offline
--force-fetch
--output <path>
--strict
--json
--allow-newer-oscal
--nist-ref <commit-or-tag>
```

`--offline` MUST rebuild from saved raw snapshots without network access.

## 16. Validation

Validation is a primary deliverable.

### 16.1 NIST OSCAL validation

Verify:

- source is valid JSON;
- required OSCAL Catalog root exists;
- metadata/version information is captured;
- declared OSCAL version is supported;
- control IDs are unique upstream;
- nested enhancement parent relationships are valid;
- local back-matter links resolve where required;
- no unsupported OSCAL structures are silently dropped.

### 16.2 Canonical ID validation

Verify deterministic mappings such as:

```text
ac-1 -> AC-01
ac-2.1 -> AC-02(01)
```

Every mapped Canadian non-400 record MUST have exactly one upstream target unless the source explicitly documents otherwise.

### 16.3 Canadian structural validation

Verify:

- exactly one canonical Canadian base record per ID;
- enhancement IDs have valid parent IDs;
- family prefixes match family;
- recognized requirement kind;
- no empty active requirement statement unless source explicitly has none;
- ODP delimiters are balanced;
- related IDs conform to accepted patterns;
- source URLs/hashes are present.

### 16.4 Reconciliation validation

Verify:

- no active record is `unresolved` in strict mode;
- all field diffs are reproducible;
- `verified_inherited` records contain no unexplained semantic differences;
- `verified_modified` records contain at least one meaningful delta;
- `verified_reclassified` records show the kind/classification change;
- `verified_canada_only` records have no NIST target;
- GC discussion never originates from NIST;
- NIST-only relationships are not silently promoted to Canadian-authoritative relationships.

### 16.5 Catalogue completeness checks

At minimum:

- all 20 family IDs are discovered in the Canadian source;
- expected NIST families are present upstream;
- family-set differences are reported;
- every Cyber Centre family page is processed;
- no page produces zero records unexpectedly.

Do not hard-code total record counts until a baseline build has been manually verified.

### 16.6 Profile completeness checks

Validate all 20 profile family tables, profile IDs, selections, enhancements, and joins against the final Canadian catalogue.

### 16.7 Semantic safety checks

Detect likely parser/reconciliation failures such as:

- navigation text inside requirements;
- one control containing the next control heading;
- discussion merged into requirement statement;
- GC discussion merged into general discussion;
- a parameter missing from one side without a recorded delta;
- a title/ID mismatch masked by fuzzy matching;
- profile table columns shifted.

### 16.8 Golden fixtures

Create offline fixtures for:

- one NIST base control with parameters;
- one nested NIST enhancement;
- one NIST record with complex nested parts;
- a Canadian inherited record;
- a Canadian modified record;
- an assurance activity reclassification;
- a 400-series Canadian base record;
- a 400-series Canadian enhancement;
- a record with GC discussion;
- a Medium-profile row with placeholder values.

## 17. Testing requirements

Use `pytest`.

### Unit tests

At minimum:

```text
OSCAL ID parser
Canadian canonical ID renderer
OSCAL -> Canadian ID mapper
nested enhancement mapping
OSCAL param normalizer
OSCAL part walker
ODP parser
statement hierarchy parser
safe comparison normalizer
field diff classifier
profile boolean normalizer
reference/back-matter resolver
hash generation
```

### NIST importer tests

Assert complete normalized objects against saved OSCAL fixtures.

### Reconciliation tests

Cover:

```text
exact/normalized inherited match
Canadian wording change
Canadian parameter change
GC-discussion-only addition
control -> activity reclassification
Canada-only 400-series item
missing NIST mapping
ambiguous mapping
```

### Parser tests

Test complete Canadian records against fixtures with explicit expected fields.

### Integration tests

From saved snapshots:

```text
NIST OSCAL snapshot
  -> import
Canadian snapshots
  -> parse
  -> reconcile
Medium profile
  -> join
  -> validate
  -> export
```

### Snapshot tests

Snapshot representative upstream, final Canadian, reconciliation, and profile JSON records.

### Property/invariant tests

Useful invariants:

```text
every Canadian enhancement has exactly one Canadian parent
every mapped non-400 Canadian record has exactly one upstream mapping
every Canada-only record lacks a NIST mapping
every profile control belongs to its declared family
every final Canadian record ID is globally unique
every Canadian ODP exists verbatim in Canadian authoritative text when the source restates it
verified_inherited records have no semantic field diff after approved normalization
```

## 18. Error handling

Define explicit exception types:

```text
FetchError
SourceChangedError
ParseError
SchemaValidationError
RelationshipResolutionError
ProfileJoinError
```

Errors MUST include:

- publication;
- source URL;
- nearest heading/control ID;
- parser stage;
- useful diagnostic context.

Never swallow parse failures and continue as if the build were complete.

A partial build MUST be marked:

```json
"validation": {
  "passed": false
}
```

---

## 19. Logging

Use structured logging.

Example:

```json
{
  "level": "INFO",
  "event": "control_parsed",
  "publication": "ITSP.10.033",
  "family": "AC",
  "id": "AC-02",
  "enhancements": 4,
  "odps": 6
}
```

At build completion log record counts and validation results.

---

## 20. Dependencies

Prefer a small dependency set.

Suggested:

```text
httpx
beautifulsoup4
lxml
pydantic>=2
typer
pyyaml
orjson
jsonschema
pandas        # only if useful for export/profile tables
openpyxl      # optional official spreadsheet importer
pytest
```

Do not add an OSCAL framework dependency unless it clearly reduces risk and is actively maintained. Plain JSON traversal plus JSON Schema validation is acceptable.

Do not use browser automation unless the public HTML cannot be retrieved normally.

Do not use LangChain/LlamaIndex for extraction or reconciliation.

## 21. Security and operational considerations

This extractor processes public UNCLASSIFIED material, but it may later be used in environments containing protected accreditation evidence.

Therefore:

- keep extraction logic independent from evidence-processing logic;
- never require uploading source or evidence to a third-party model provider;
- make embedding provider optional;
- support local/offline embedding later;
- do not add telemetry by default;
- do not send document content to external services as part of parsing;
- pin dependencies via a lockfile;
- include dependency vulnerability scanning in CI where practical.

---

## 22. Copyright, attribution, and source integrity

Preserve official source attribution and URLs in every derived dataset.

Do not present normalized or AI-enriched text as verbatim Cyber Centre text.

Keep authoritative source fields separate from any future:

```text
summary
keywords
evidence_examples
AI-generated mappings
classifier labels
```

Any future enrichment MUST include metadata such as:

```json
{
  "derived": true,
  "generator": "...",
  "generator_version": "...",
  "generated_at": "..."
}
```

---

## 23. CI

Create a CI workflow that runs:

```text
ruff/lint
type checking
pytest
offline NIST OSCAL fixture import
offline Canadian fixture build
reconciliation validation
JSON Schema validation
OSCAL-compatible export validation where supported
```

Network-based source freshness checks SHOULD be a separate scheduled/manual job.

A scheduled source-watch workflow MAY:

1. check the configured NIST ref / resolve current commit;
2. compare NIST OSCAL metadata/version/hash;
3. fetch Cyber Centre source hashes;
4. report changed sources independently;
5. avoid automatically accepting new reconciliations;
6. require review before committing changed derived catalogues.

## 24. README requirements

`README.md` MUST include:

1. project purpose;
2. the NIST-baseline / Canadian-overlay architecture;
3. authority rules;
4. install instructions;
5. exact build commands;
6. source/version pinning behavior;
7. output files;
8. record and reconciliation schema examples;
9. how to inspect a control and its NIST lineage;
10. how to render embedding records;
11. how to rebuild offline;
12. how to diff two source versions;
13. known limitations.

Example quick start:

```bash
uv sync
uv run itsp-kb fetch
uv run itsp-kb build
uv run itsp-kb show AC-02
uv run itsp-kb show AC-02 --upstream
uv run itsp-kb render-embeddings --view requirement_only
```

## 25. Implementation phases

Claude Code should implement the project in these phases and keep the repository runnable at the end of each phase.

### Phase 1 — Scaffold, source registry, and reproducible fetch

Deliver:

- project structure;
- typed config;
- CLI shell;
- source registry;
- NIST and Cyber Centre fetchers;
- resolved NIST commit/version capture;
- raw source snapshots;
- hashing/provenance;
- basic tests.

Acceptance:

```bash
itsp-kb fetch
```

snapshots both NIST OSCAL and Cyber Centre sources with hashes and provenance.

### Phase 2 — NIST OSCAL normalized baseline

Deliver:

- OSCAL metadata parser;
- groups/families;
- controls;
- nested enhancements;
- params;
- parts;
- links/back-matter;
- canonical ID mapper;
- normalized upstream JSONL.

Acceptance:

- upstream IDs are unique;
- representative NIST controls/enhancements match OSCAL source;
- unsupported structures are reported rather than dropped;
- tests pass offline.

### Phase 3 — Canadian overlay and reconciliation

Deliver:

- Cyber Centre family discovery;
- Canadian field extraction;
- Control/Activity classification;
- GC discussion;
- 400-series content;
- field-level reconciliation;
- final Canadian records;
- reconciliation report.

Acceptance:

- every active non-400 Canadian record is mapped or fails strict validation;
- 400-series records are captured as Canada-only;
- representative inherited/modified/reclassified records are manually verified;
- no duplicate canonical IDs.

### Phase 4 — Medium profile

Deliver:

- profile table parser/importer;
- join to reconciled Canadian catalogue;
- profile membership projection;
- profile JSONL/CSV;
- optional OSCAL-compatible profile export.

Acceptance:

- every profile row resolves or fails;
- selected/unselected states match source;
- placeholder values are preserved.

### Phase 5 — Graph, embeddings, and Canadian OSCAL-compatible export

Deliver:

- Canadian-authoritative relationship edges;
- upstream relationship dataset;
- deterministic embedding text renderer;
- embedding views;
- derived Canadian OSCAL Catalog export.

Acceptance:

```bash
itsp-kb render-embeddings --view requirement_only
```

generates one deterministic record per supported Canadian semantic unit.

### Phase 6 — Version diff and hardening

Deliver:

- build manifest;
- separate upstream/Canadian/final hashes;
- diff command;
- source-layout/schema failure detection;
- CI;
- documentation.

Acceptance:

Two builds from identical snapshots produce no semantic diff.

### Phase 7 — Optional lifecycle/assessment extensions

Only after Phases 1–6 are stable.

Add ITSP.10.036, ITSP.10.037, and ITSP.10.033-02 using document-specific schemas.

## 26. Manual verification checklist

Before declaring v1 complete, manually inspect records representing each reconciliation class.

At minimum inspect:

```text
AC-01
AC-02
CA-02
CP-09
PL-10
one PM record
one PT record
one SR record
one assurance activity mapped from NIST
one Canadian 400-series base record
one Canadian 400-series enhancement
```

For each compare:

```text
NIST OSCAL ID
Canadian ID
name/title
control/activity classification
normative statements
nested statement structure
parameters/ODPs
discussion
GC discussion
related controls/activities
references
enhancements
reconciliation status
field-level deltas
Medium-profile selection
Medium-profile placeholder values
```

Document verification results in `docs/VERIFICATION.md`.

## 27. Acceptance criteria for v1

v1 is complete only when all of the following are true:

- [ ] Official NIST SP 800-53 Rev. 5 OSCAL JSON is used as the structured upstream baseline.
- [ ] NIST source commit, metadata version, OSCAL version, and SHA-256 are recorded.
- [ ] Official Cyber Centre content remains authoritative for the final ITSP dataset.
- [ ] Raw snapshots of both source authorities are retained.
- [ ] The source registry is centralized.
- [ ] NIST groups/controls/enhancements/params/parts are imported without silent semantic loss.
- [ ] OSCAL-to-Canadian ID mapping is deterministic and tested.
- [ ] All 20 ITSP.10.033 families are discovered and compared with the NIST family set.
- [ ] Every active non-400 Canadian record is reconciled to exactly one NIST record or explicitly fails validation.
- [ ] Every final record has an origin and reconciliation status.
- [ ] Base controls and activities are independently structured.
- [ ] Enhancements are independently addressable.
- [ ] Controls and assurance activities remain distinguishable.
- [ ] ODPs are first-class structured objects and reconciled with NIST params.
- [ ] General discussion and GC discussion are separate.
- [ ] Related controls are parsed and exported as Canadian-authoritative edges.
- [ ] NIST-only edges remain distinguishable from Canadian-authoritative edges.
- [ ] References are preserved with source lineage.
- [ ] 400-series Canadian content is captured as Canada-only.
- [ ] Medium-profile tables/spreadsheet are parsed.
- [ ] Medium-profile selections join to final Canadian records.
- [ ] Suggested placeholder values and profile notes are preserved.
- [ ] JSONL is emitted as the canonical simplified interchange format.
- [ ] CSV convenience exports are produced.
- [ ] A derived OSCAL-compatible Canadian catalogue is produced and clearly labeled non-official.
- [ ] Embedding-ready deterministic Canadian text is produced.
- [ ] No embedding provider is required.
- [ ] Provenance exists for NIST, Canadian, and reconciled layers.
- [ ] Rebuilds are idempotent.
- [ ] Offline builds from snapshots work.
- [ ] NIST and Canadian source changes can be diffed independently.
- [ ] Parser/schema/reconciliation failures fail strict validation.
- [ ] Automated tests cover inherited, modified, reclassified, and Canada-only cases.
- [ ] Manual verification against both NIST OSCAL and Cyber Centre source has been documented.

## 28. Explicit non-goals for v1

Do NOT spend initial implementation effort on:

- a web UI;
- a vector database;
- an LLM agent;
- automatic security-control compliance judgments;
- automatically generating missing accreditation evidence;
- automatic tailoring decisions;
- replacing a qualified security assessor;
- parsing arbitrary third-party security frameworks;
- graph databases;
- French extraction unless it falls out cheaply from the architecture.

The first product is a **high-integrity structured corpus**.

---

## 29. Intended next-stage architecture

The structured corpus should support a later evidence-assessment system:

```text
 NIST OSCAL baseline             Cyber Centre ITSP
 ┌────────────────┐              ┌─────────────────┐
 │ controls       │              │ Canadian text   │
 │ enhancements   │              │ activities      │
 │ params         │              │ GC discussion   │
 │ parts          │              │ 400-series      │
 └───────┬────────┘              └────────┬────────┘
         │                                │
         └────────── reconciliation ──────┘
                         │
                         ▼
              Canadian structured corpus
              ┌─────────────────────────┐
              │ controls                │
              │ activities              │
              │ enhancements            │
              │ ODPs                    │
              │ profiles                │
              │ relationships           │
              │ source lineage/deltas   │
              │ assessment guidance     │
              └────────────┬────────────┘
                           │
                           ▼
                    hybrid retrieval
                 metadata + BM25/vector
                           │
                           ▼
Evidence document -> chunk/extract -> candidate controls
                           │
                           ▼
                    evidence evaluator
                           │
               ┌───────────┼────────────┐
               ▼           ▼            ▼
            evidence    coverage     missing evidence
            citation    status       / uncertainty
```

The extractor MUST enable this architecture without implementing the evaluator itself.

## 30. Recommended future evidence mapping object

Reserve a downstream schema similar to:

```json
{
  "control_id": "AC-02",
  "evidence": [
    {
      "artifact_id": "SSP-001",
      "location": {
        "page": 37,
        "section": "Account Management"
      },
      "quote_or_span": "...",
      "evidence_type": "policy | configuration | procedure | test | record | other"
    }
  ],
  "assessment": {
    "status": "supported | partially_supported | unsupported | not_assessed",
    "confidence": 0.0,
    "missing_evidence": [],
    "notes": []
  }
}
```

This object is intentionally outside the authoritative extraction schema.

---

## 31. Instructions to Claude Code

When implementing this specification:

1. Start by importing the official NIST OSCAL JSON; do not begin by rebuilding NIST controls from Cyber Centre HTML.
2. Record the NIST OSCAL metadata version, OSCAL version, resolved Git commit, and source hash before parsing.
3. Preserve unknown OSCAL properties/parts rather than dropping them.
4. Implement and test OSCAL-to-Canadian canonical ID mapping before Canadian reconciliation.
5. Inspect the live Cyber Centre HTML before writing production selectors.
6. Treat the Cyber Centre as authoritative for final Canadian wording/classification.
7. Never assume a same-ID NIST record is textually identical to ITSP.10.033; reconcile it.
8. Never use fuzzy matching to silently finalize a control mapping.
9. Parse Canadian 400-series records fully as Canada-only content.
10. Keep upstream NIST, Canadian source, reconciliation, and final derived representations as separate layers.
11. Add a fixture whenever an unusual OSCAL or Cyber Centre pattern is discovered.
12. Never silently discard content that does not fit the current schema.
13. Prefer an explicit `unmapped` field or hard error over guessing.
14. Keep authoritative and derived fields visibly separate.
15. Run tests after each implementation phase.
16. Update `README.md` and `docs/VERIFICATION.md` at the end of each phase.
17. Do not declare the extractor complete until representative records have been compared manually against both NIST OSCAL and the Cyber Centre publication.

## 32. Authoritative references used to design this specification

### Canadian Centre for Cyber Security

- Cyber security and privacy risk management: A lifecycle approach  
  `https://www.cyber.gc.ca/en/guidance/cyber-security-privacy-risk-management`

- Security and privacy controls and assurance activities catalogue (ITSP.10.033)  
  `https://www.cyber.gc.ca/en/guidance/cyber-security-privacy-risk-management/itsp10033`

- ITSP.10.033 — Foreword, overview and introduction  
  `https://www.cyber.gc.ca/en/guidance/cyber-security-privacy-risk-management/itsp10033/foreword-overview-introduction`

- ITSP.10.033 — Concepts and structure  
  `https://www.cyber.gc.ca/en/guidance/cyber-security-privacy-risk-management/itsp10033/concepts-structure`

- ITSP.10.033 — Controls and assurance activities families  
  `https://www.cyber.gc.ca/en/guidance/cyber-security-privacy-risk-management/itsp10033/controls-assurance-activities-families`

- Suggested organizational security and privacy control and activity profile — Medium impact (ITSP.10.033-01)  
  `https://www.cyber.gc.ca/en/guidance/cyber-security-privacy-risk-management/suggested-organizational-security-privacy-control-activity-profile-medium-impact-itsp10033-01`

- Organizational cyber security and privacy risk management activities (ITSP.10.036)  
  `https://www.cyber.gc.ca/en/guidance/cyber-security-privacy-risk-management/organizational-cyber-security-privacy-risk-management-activities-itsp10036`

### NIST OSCAL

- Official OSCAL content repository  
  `https://github.com/usnistgov/oscal-content`

- NIST SP 800-53 Rev. 5 OSCAL JSON catalogue  
  `https://github.com/usnistgov/oscal-content/blob/main/nist.gov/SP800-53/rev5/json/NIST_SP-800-53_rev5_catalog.json`

- OSCAL Catalog model reference  
  `https://pages.nist.gov/OSCAL-Reference/models/v1.2.3/catalog/json-reference/`

- OSCAL Catalog model concepts  
  `https://pages.nist.gov/OSCAL/learn/concepts/layer/control/catalog/`

The final ITSP catalogue MUST treat the Cyber Centre source itself as authoritative for Canadian content. The NIST OSCAL file is the structured upstream baseline and validation/reconciliation source for NIST-derived content.

