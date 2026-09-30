# Agent instructions for dataset contributions

You are assisting a user who is adding smart-contract audit findings to this repository.

## Safe contribution workflow

1. Inspect the supplied files, schema, encoding, and representative records first.
2. Require and record a source URL or repository link, plus version, commit, or download
   date when available.
3. Explain the proposed field mapping before making assumptions about ambiguous fields.
4. Create a dataset-specific Python adapter under `adapters/`; do not force unrelated
   source formats through an existing adapter.
5. Preserve the original input and write intermediate output to a separate staging path.
6. Map records to the canonical fields documented in `CONTRIBUTING.md`.
7. Preserve unmapped source fields in `raw_record`.
8. Validate row counts, IDs, required fields, malformed records, and duplicate counts.
9. Remove exact duplicates only. Keep near-duplicates; do not delete them automatically.
10. Add or update the existing Markdown findings and `index.jsonl` without changing
   existing IDs.
11. Summarize all changes, skipped records, assumptions, provenance, and unresolved
    ambiguities.

Use `templates/finding_template.md` when creating a Markdown finding manually. Keep the
frontmatter limited to the stable ID and severity; keep provenance in `index.jsonl`.

## Data integrity rules

- Never overwrite source datasets.
- Never invent vulnerability details, PoCs, severities, or recommendations.
- Do not use filename similarity as proof that findings are duplicates.
- Keep derived or generated content clearly labeled.
- Do not silently discard unknown fields.
- If a mapping or deduplication decision could materially change the dataset, stop and
  ask the user before proceeding.

## Search and output guidance

For the existing agent dataset, search titles first, then use `index.jsonl` metadata,
then open the relevant Markdown files. Cite stable finding IDs and paths in reports.
