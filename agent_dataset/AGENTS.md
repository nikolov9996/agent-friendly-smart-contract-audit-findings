# Search instructions for the audit findings dataset

This directory contains one Markdown file per finding and a compact `index.jsonl`.

## Retrieval workflow

1. Search titles first to identify the main vulnerability concept.
2. Use `index.jsonl` metadata such as `severity` and `source_file` to narrow the
   title matches.
3. Use the returned `path` to open only the relevant files in `findings/`.
4. Search descriptions, PoCs, and recommendations by keyword when title matching is
   insufficient.
4. Compare multiple findings when the query is broad, and avoid returning exact or
   near-identical findings more than once.
5. Cite findings by their stable `id` and Markdown path.

## Field guidance

- `severity` is the normalized severity when available.
- `source_file` is a provenance field stored in `index.jsonl`, not in the Markdown
  frontmatter.
- `Derived Narrative` is derived content and may not be source-grounded. Prefer the
  original `Description`, `Proof of Concept`, and `Recommendation` sections.

## Output expectations

When reporting results, include the finding ID, title, severity, and Markdown path. State
when a result is based only on keyword similarity or incomplete evidence.
