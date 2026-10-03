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

The import process should map source data to these fields when available:

- `source_dataset`
- `source_record_id`
- `title`
- `description`
- `poc`
- `recommendation`
- `severity`
- `severity_normalized`
- `severity_candidates`
- `source_file`
- `raw_record`

Missing fields should remain empty. Unknown fields should be preserved in `raw_record`
rather than silently discarded.

## Severity normalization

Keep `severity` as the existing reported/display label and preserve exact original
labels in the raw source records. Markdown frontmatter still contains only `id` and
`severity`. The index adds two derived fields for consistent severity searches:

- `severity_normalized`: `Critical`, `High`, `Medium`, `Low`, or `Informational`;
  use JSON `null` when the source label does not identify one canonical tier.
- `severity_candidates`: an ordered list of possible canonical tiers. A resolved
  label has one candidate matching `severity_normalized`; a combined label has two;
  an unrecognized label has an empty list and `severity_normalized: null`.

These fields are required in every index entry. The compact index contains `id`,
`severity`, `severity_normalized`, `severity_candidates`, `title`, `path`,
`description_length`, `recommendation_length`, and `source_file`. Preserve the
remaining canonical source fields in the original or intermediate records.

Use [`severity_policy.py`](severity_policy.py) as the shared mapping for imports
and validation. Matching ignores case and surrounding whitespace without
changing the stored label. The approved mappings are:

| Reported label or alias | `severity_normalized` | `severity_candidates` |
| --- | --- | --- |
| `Critical`, `Critical Risk` | `Critical` | `["Critical"]` |
| `High`, `High Risk` | `High` | `["High"]` |
| `Medium`, `Medium Risk` | `Medium` | `["Medium"]` |
| `Low`, `Low Risk` | `Low` | `["Low"]` |
| `Informational`, `Info` | `Informational` | `["Informational"]` |
| `Crit/High` | `null` | `["Critical", "High"]` |
| `Low/Info` | `null` | `["Low", "Informational"]` |
| Any other non-empty label | `null` | `[]` |

Candidate order follows the table. An unknown label is preserved and reported as
unmapped; an empty or missing reported severity is rejected. Never select one tier
from a combined label using its title, impact keywords, or finding-ID prefix alone.
Normalization expresses the source classification; it does not reassess risk or
establish that different sources use the same severity rubric. Resolving a combined
label requires source-backed review and a separately documented policy update.

### Adding and validating normalized metadata

Populate both derived fields in the chosen import or conversion process using the
shared policy. Run from the repository root; only the Python standard library is
required:

```python
from severity_policy import normalize_severity

row["severity_normalized"], row["severity_candidates"] = normalize_severity(row["severity"])
```

Keep the original input unchanged and write the proposed index to a separate
staging path. Validate it against the existing finding files, for example:

```bash
python3 validate_agent_dataset.py --index /tmp/severity-normalization/index.jsonl
```

The validator requires the nine-field index schema, checks derived severity metadata
against the shared policy, and reports structural errors, duplicate IDs or paths,
and duplicate JSON keys. Investigate unexpected fields and preserve them in the
source/intermediate records before changing a schema. Report ambiguous or unmapped
labels without assigning unsupported tiers.

Before promoting staged output, compare record counts, IDs, paths, and all original
fields with the input; verify that Markdown and raw sources are unchanged. Save a
copy of the original index and conversion notes alongside the staged output. Existing
consumers of `severity` can continue to use it, while consumers enforcing the old
seven-field index schema need updating. After promotion, run:

```bash
python3 validate_agent_dataset.py
```

## Import process

1. Choose a suitable conversion method. Manual conversion or a temporary script is
   acceptable when simpler.
2. Convert the source into the canonical intermediate format.
3. Validate record counts, required fields, encoding, and malformed records. After
   updating the dataset, run `python3 validate_agent_dataset.py` to check that
   `index.jsonl` and the Markdown findings follow the repository structure.
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
