# Dataset search instructions

Use this directory as your working area for finding searches and reports. Read
[`README.md`](README.md) for copyable search commands; all paths there are relative
to this directory. The normal retrieval workflow uses only the files here. Consult
repository contribution and maintenance instructions when the user requests those
tasks.

- Treat `index.jsonl` and finding files as read-only during retrieval.
- Search titles first; broaden with related vulnerability and mechanism terms.
- Use `index.jsonl` metadata to narrow results, then open the referenced Markdown.
- Verify the root cause in context. A keyword match alone is not evidence of applicability.
- Exclude `Derived Narrative` sections from full-text search matches and supporting
  evidence; use the original finding sections.
- Cite findings by ID and path.
