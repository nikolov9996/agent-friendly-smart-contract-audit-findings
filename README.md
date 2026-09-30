# Agent-Friendly Smart Contract Audit Dataset

This repository contains a structured, agent-friendly collection of smart-contract
audit findings. Each finding is stored as an individual Markdown file, with a compact
`index.jsonl` for title-first and metadata-based search.

Keywords: smart-contract audit findings, Solidity vulnerabilities, DeFi security,
vulnerability reports, proof-of-concept exploits, audit recommendations, searchable
Markdown dataset, JSONL metadata index, and agent-assisted security research.

The project is inspired by the
[Zaevlad audit findings dataset](https://huggingface.co/datasets/Zaevlad/audit-findings-dataset).

## Repository structure

```text
agent_dataset/
├── AGENTS.md
├── README.md
├── index.jsonl
└── findings/
    └── finding-XXXXXX.md
```

Use the repository-level [AGENTS.md](AGENTS.md) and
[CONTRIBUTING.md](CONTRIBUTING.md) before adding records. Every contribution must
include a source URL or repository link and preserve provenance.

The dataset is intended for agent-assisted search and defensive smart-contract security
research. It is not a substitute for independent audit verification.
