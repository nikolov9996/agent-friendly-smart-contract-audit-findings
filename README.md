# Agent-Friendly Smart Contract Audit Dataset

This repository contains a structured, agent-friendly collection of smart-contract
audit findings. Each finding is stored as an individual Markdown file, with a compact
`index.jsonl` for title-first and metadata-based search.

For finding searches and audit reports, start in [`agent_dataset/`](agent_dataset/).
Read its [agent instructions](agent_dataset/AGENTS.md) and
[search guide](agent_dataset/README.md), and run the search examples from that
directory. The normal retrieval workflow stays within `agent_dataset/`.

Keywords: smart-contract audit findings, Solidity vulnerabilities, DeFi security,
vulnerability reports, proof-of-concept exploits, audit recommendations, searchable
Markdown dataset, JSONL metadata index, and agent-assisted security research.

The project is inspired by the
[Zaevlad audit findings dataset](https://huggingface.co/datasets/Zaevlad/audit-findings-dataset).

Additional findings come from the
[0xSimao Findings Database](https://0xsimao.com/findings), preserved in
[`raw_records/simao_findings.parquet`](raw_records/simao_findings.parquet).

## Repository structure

```text
.
├── AGENTS.md
├── CONTRIBUTING.md
├── README.md
├── validate_agent_dataset.py
├── agent_dataset/
│   ├── AGENTS.md
│   ├── README.md
│   ├── index.jsonl
│   └── findings/              # one Markdown file per finding
├── raw_records/               # source datasets, preserved as supplied
└── templates/
    └── finding_template.md
```

## Contributing and maintaining the dataset

Use the repository-level [AGENTS.md](AGENTS.md) and
[CONTRIBUTING.md](CONTRIBUTING.md) before adding records. Every contribution must
include a source URL or repository link and preserve provenance.

Run `python3 validate_agent_dataset.py` to check that the main dataset index and
finding files follow the repository structure.

The dataset is intended for agent-assisted search and defensive smart-contract security
research. It is not a substitute for independent audit verification.
