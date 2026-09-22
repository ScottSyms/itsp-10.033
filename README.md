# itsp-knowledge-base

A deterministic pipeline that builds a structured Canadian ITSP.10.033 knowledge base by combining
the official NIST SP 800-53 Rev. 5 OSCAL catalogue (structured baseline) with the official Canadian
Centre for Cyber Security ITSP.10.033 publications (authoritative Canadian overlay).

> Status: under active implementation. This README is filled in incrementally at the end of each
> build phase; see `specification.md` for the full design and `docs/VERIFICATION.md` for manual
> verification results once available.

## Quick start

```bash
mise install
uv sync
uv run itsp-kb fetch
uv run itsp-kb build
uv run itsp-kb show AC-02
uv run itsp-kb show AC-02 --upstream
uv run itsp-kb render-embeddings --view requirement_only
uv run pytest
```
