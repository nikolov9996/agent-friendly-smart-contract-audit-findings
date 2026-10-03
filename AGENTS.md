# Agent instructions

## Default workflow: finding retrieval

For searching, reading, or reporting audit findings, go directly to `agent_dataset/`.
Read `agent_dataset/AGENTS.md` and `agent_dataset/README.md`, and use that directory
as your working area. Focus repository reads and searches on its `index.jsonl` and
`findings/`; the normal retrieval workflow does not need contribution instructions,
raw source datasets, templates, or maintenance scripts. Treat the dataset as read-only
unless the user requests changes.

Start by searching finding titles. After that, choose the search method that best fits
the question; for example, use `index.jsonl` to filter or locate findings and open the
relevant Markdown files for full details. This is guidance, not a required fixed
sequence. Exclude `Derived Narrative` sections from full-text search matches and
supporting evidence; use the original finding sections. Cite stable finding IDs and
paths in reports.

## Contribution and maintenance workflow

Apply the following instructions when the user requests importing, editing, or
maintaining the dataset. Read `CONTRIBUTING.md` for those tasks.

### Safe contribution workflow

1. Inspect the supplied files, schema, encoding, and representative records first.
2. Require and record a source URL or repository link, plus version, commit, or download
   date when available.
3. Explain the proposed field mapping before making assumptions about ambiguous fields.
4. Choose a suitable conversion method; manual conversion or a one-off script is
   acceptable when simpler.
5. Preserve the original input and write intermediate output to a separate staging path.
6. Map records to the canonical fields documented in `CONTRIBUTING.md`.
7. Preserve unmapped source fields in `raw_record`.
8. Validate row counts, IDs, required fields, malformed records, and duplicate counts.
   After updating the dataset, run `python3 validate_agent_dataset.py` to check the
   `agent_dataset` index and Markdown structure.
9. Remove exact duplicates only. Keep near-duplicates; do not delete them automatically.
10. Add or update the existing Markdown findings and `index.jsonl` without changing
   existing IDs.
11. Summarize all changes, skipped records, assumptions, provenance, and unresolved
    ambiguities.

Use `templates/finding_template.md` when creating a Markdown finding manually. Keep the
frontmatter limited to the stable ID and severity; keep provenance in `index.jsonl`.

### Data integrity rules

- Never overwrite source datasets.
- Never invent vulnerability details, PoCs, severities, or recommendations.
- Do not use filename similarity as proof that findings are duplicates.
- Keep derived or generated content clearly labeled.
- Do not silently discard unknown fields.
- If a mapping or deduplication decision could materially change the dataset, stop and
  ask the user before proceeding.
