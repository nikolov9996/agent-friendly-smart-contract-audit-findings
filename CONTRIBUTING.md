# Contributing audit findings

This repository accepts audit findings from CSV, JSON, JSONL, Parquet, spreadsheets,
Markdown, or other structured sources.

## Before importing data

Keep the original dataset unchanged. Place a copy or reference to the source in a
separate working area and record its provenance. Every contribution must provide a
source URL or repository link. Also record the source version, commit, or download date
when available. Inspect the schema and sample records before deciding how fields map to
the repository format.

## Canonical finding fields

An import adapter should map source data to these fields when available:

- `source_dataset`
- `source_record_id`
- `title`
- `description`
- `poc`
- `recommendation`
- `severity`
- `source_file`
- `raw_record`

Missing fields should remain empty. Unknown fields should be preserved in `raw_record`
rather than silently discarded.

## Import process

1. Add a dataset-specific adapter under `adapters/`, for example
   `adapters/import_example_audit.py`.
2. Convert the source into the canonical intermediate format.
3. Validate record counts, required fields, encoding, and malformed records.
4. Remove only exact duplicates. Keep near-duplicates unless the user explicitly
   requests a separate review.
5. Assign stable IDs without changing existing IDs.
6. Add or update the existing Markdown findings and update `index.jsonl`.
7. Report imported, skipped, malformed, and duplicate records.

## Important rules

- Never overwrite original source files.
- Never merge records solely because filenames share a prefix or chunk number.
- Do not rewrite or embellish source descriptions during import.
- Keep generated or derived text clearly labeled.
- Preserve source provenance for every finding.
- Every contribution must include a source URL or repository link in its provenance
  notes or index metadata.
- New contributions must update the existing Markdown dataset and `index.jsonl`.
- Near-duplicates are retained; only exact duplicates are removed.
- Do not silently guess ambiguous field mappings; document or ask about them.

## Expected output

The generated dataset should contain one Markdown file per finding and a matching
`index.jsonl` entry. The Markdown file uses stable IDs and preserves the original
finding sections. The index provides compact metadata and the path to the Markdown file.

Use [`templates/finding_template.md`](templates/finding_template.md) when creating a
finding manually. Provenance fields belong in `index.jsonl`, not in the Markdown
frontmatter.
