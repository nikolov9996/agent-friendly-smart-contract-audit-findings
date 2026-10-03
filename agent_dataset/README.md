# Searching Findings

Use `agent_dataset/` as your working area for finding searches and reports. If starting
at the repository root, run `cd agent_dataset` first. All commands below use the Python
standard library and paths relative to this directory. Search titles first, then
finding text; open only likely matches and verify the root cause in context.

Search titles in `index.jsonl` (Python standard library, case-insensitive):

```bash
python3 - <<'PY'
import json

terms = ("rounding", "precision loss", "share inflation")
with open("index.jsonl", encoding="utf-8") as index_file:
    for line in index_file:
        finding = json.loads(line)
        if any(term.casefold() in finding["title"].casefold() for term in terms):
            normalized = finding["severity_normalized"] or "unresolved"
            candidates = ", ".join(finding["severity_candidates"]) or "unmapped"
            print(f'{finding["id"]}\t{finding["severity"]}\t'
                  f'{normalized}\t{candidates}\t'
                  f'{finding["title"]}\t{finding["path"]}')
PY
```

The columns are ID, reported severity, normalized severity, candidates, title, and
path. `severity` preserves the existing reported/display label. Normalized severity
uses `Critical`, `High`, `Medium`, `Low`, or `Informational`; unresolved labels use
JSON `null`. Combined labels retain their possible tiers in `severity_candidates`.
Unrecognized labels have an empty candidate list and are shown as `unmapped`.

## Filtering by severity

Use this title search to filter by a canonical tier. Set `include_ambiguous = False`
for exact matches, or `True` to also include combined labels containing that tier.
Set `terms = ()` to search all titles at the selected severity. Severity input ignores
case and surrounding whitespace, so `High`, `high`, and ` HIGH ` match the same tier.

```bash
python3 - <<'PY'
import json

terms = ("rounding", "precision loss", "share inflation")
severity = "High"
severity_key = severity.strip().casefold()
include_ambiguous = True
with open("index.jsonl", encoding="utf-8") as index_file:
    for line in index_file:
        finding = json.loads(line)
        title_matches = not terms or any(
            term.casefold() in finding["title"].casefold() for term in terms
        )
        severity_matches = (
            any(candidate.casefold() == severity_key
                for candidate in finding["severity_candidates"])
            if include_ambiguous
            else finding["severity_normalized"] is not None
            and finding["severity_normalized"].casefold() == severity_key
        )
        if title_matches and severity_matches:
            normalized = finding["severity_normalized"] or "unresolved"
            candidates = ", ".join(finding["severity_candidates"]) or "unmapped"
            print(f'{finding["id"]}\t{finding["severity"]}\t'
                  f'{normalized}\t{candidates}\t'
                  f'{finding["title"]}\t{finding["path"]}')
PY
```

For the 1,482-record index, all-title exact High filtering returns 659
findings; including ambiguous High candidates returns 815. The extra 156 retain the
reported label `Crit/High` and are not classified as confirmed High findings. The
387 `Low/Info` entries similarly remain unresolved between Low and Informational.
Candidate counts overlap across tiers and must not be summed as exclusive totals.
Unmapped labels match no tier and should be reviewed separately. To locate every
unresolved record, filter on `finding["severity_normalized"] is None`.

Severity matching ignores case and surrounding whitespace. Canonical labels resolve
to their corresponding tiers; `Critical Risk`, `High Risk`, `Medium Risk`, and
`Low Risk` are aliases for those tiers, and `Info` resolves to `Informational`.
`Crit/High` retains candidates `Critical` and `High`; `Low/Info` retains candidates
`Low` and `Informational`. Preserve the reported label in citations and never infer
one tier from a combined label. Normalization reflects reported classifications;
sources may use different severity rubrics.

## Broadening to finding text

If title search is too narrow, search the original finding sections with related
terms. Exclude `Derived Narrative` from search matches and supporting evidence:

```bash
python3 - <<'PY'
import re
from pathlib import Path

terms = ("rounding", "precision loss", "share inflation")
derived_note = "The following field is derived content and may not be source-grounded:"
for path in sorted(Path("findings").glob("finding-*.md")):
    in_derived = False
    fence_end = None
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, 1):
        heading = re.match(
            r"^ {0,3}(#{1,2})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$", line
        )
        derived_heading = heading and heading[2].casefold() == "derived narrative"
        if derived_heading and (
            fence_end is None
            or next((text.strip() for text in lines[line_number:] if text.strip()), "")
            == derived_note
        ):
            in_derived = True
            fence_end = None
        elif fence_end is not None:
            if fence_end.fullmatch(line):
                fence_end = None
        else:
            fence = re.match(r" {0,3}(`{3,}|~{3,})", line)
            if fence:
                fence_end = re.compile(
                    rf" {{0,3}}{fence[1][0]}{{{len(fence[1])},}}[ \t]*"
                )
            elif heading:
                in_derived = False
        if not in_derived and any(term.casefold() in line.casefold() for term in terms):
            print(f"{path}:{line_number}:{line}")
PY
```

The command uses only the Python standard library and prints dataset-relative
paths with original line numbers. It skips the derived section and its subsections,
resuming at the next level-one or level-two heading. Headings inside fenced code
blocks do not change the active section, except that a derived heading followed by
the standard derived-content disclaimer identifies the boundary even if an original
code fence was left unclosed.

Index paths and full-text search results are relative to this directory; open them
directly (for example, `findings/finding-025000.md`). Cite findings by stable ID and
path; use the `agent_dataset/` prefix when citing a path relative to the repository
root. Treat keyword matches as leads, not proof that a finding applies.
`Derived Narrative`, when present, is generated content and is excluded from this
workflow.
