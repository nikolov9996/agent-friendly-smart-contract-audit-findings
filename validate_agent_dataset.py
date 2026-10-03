#!/usr/bin/env python3
"""Validate the repository's agent_dataset index and finding files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from severity_policy import severity_metadata_errors


EXPECTED_FIELDS = frozenset({
    "id",
    "severity",
    "severity_normalized",
    "severity_candidates",
    "title",
    "path",
    "description_length",
    "recommendation_length",
    "source_file",
})
EXPECTED_FRONTMATTER_FIELDS = frozenset({"id", "severity"})
REQUIRED_SECTIONS = ("Description", "Proof of Concept", "Recommendation")
FINDING_PATH = re.compile(r"findings/finding-(\d+)\.md\Z")


def reject_duplicate_json_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Prevent json.loads from silently discarding duplicate object keys."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def parse_frontmatter(text: str) -> dict[str, str] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None

    values: dict[str, str] = {}
    for line in lines[1:end]:
        key, separator, value = line.partition(":")
        if not separator:
            continue
        key = key.strip()
        value = value.strip()
        if value.startswith('"') and value.endswith('"'):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                pass
        values[key] = value
    return values


def validate(dataset: Path, index_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    if index_path is None:
        index_path = dataset / "index.jsonl"
    if not index_path.is_file():
        return [f"missing {index_path}"]

    seen_ids: set[int] = set()
    seen_paths: set[str] = set()
    indexed_paths: set[str] = set()

    for line_number, line in enumerate(index_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            errors.append(f"index.jsonl:{line_number}: blank lines are not allowed")
            continue
        try:
            row = json.loads(line, object_pairs_hook=reject_duplicate_json_keys)
        except json.JSONDecodeError as exc:
            errors.append(f"index.jsonl:{line_number}: invalid JSON: {exc.msg}")
            continue
        except ValueError as exc:
            errors.append(f"index.jsonl:{line_number}: invalid JSON: {exc}")
            continue
        if not isinstance(row, dict):
            errors.append(f"index.jsonl:{line_number}: each record must be a JSON object")
            continue

        keys = set(row)
        if keys != EXPECTED_FIELDS:
            missing = sorted(EXPECTED_FIELDS - keys)
            extra = sorted(keys - EXPECTED_FIELDS)
            errors.append(
                f"index.jsonl:{line_number}: field mismatch; missing={missing}, extra={extra}"
            )

        finding_id = row.get("id")
        if not isinstance(finding_id, int) or isinstance(finding_id, bool) or finding_id <= 0:
            errors.append(f"index.jsonl:{line_number}: id must be a positive integer")
            finding_id = None
        elif finding_id in seen_ids:
            errors.append(f"index.jsonl:{line_number}: duplicate id {finding_id}")
        else:
            seen_ids.add(finding_id)

        for field in ("severity", "title", "path", "source_file"):
            if not isinstance(row.get(field), str) or not row[field].strip():
                errors.append(f"index.jsonl:{line_number}: {field} must be a non-empty string")
        for error in severity_metadata_errors(row):
            errors.append(f"index.jsonl:{line_number}: {error}")
        for field in ("description_length", "recommendation_length"):
            value = row.get(field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                errors.append(f"index.jsonl:{line_number}: {field} must be a non-negative integer")

        relative_path = row.get("path")
        if not isinstance(relative_path, str):
            continue
        if relative_path in seen_paths:
            errors.append(f"index.jsonl:{line_number}: duplicate path {relative_path!r}")
        seen_paths.add(relative_path)
        indexed_paths.add(relative_path)

        match = FINDING_PATH.fullmatch(relative_path)
        if not match:
            errors.append(
                f"index.jsonl:{line_number}: path must look like findings/finding-<id>.md"
            )
            continue
        if finding_id is not None and int(match.group(1)) != finding_id:
            errors.append(f"index.jsonl:{line_number}: path ID does not match id {finding_id}")
        elif finding_id is not None:
            expected_path = f"findings/finding-{finding_id:06d}.md"
            if relative_path != expected_path:
                errors.append(
                    f"index.jsonl:{line_number}: path must be {expected_path!r} for id {finding_id}"
                )

        markdown_path = dataset / relative_path
        if not markdown_path.is_file():
            errors.append(f"index.jsonl:{line_number}: missing finding file {relative_path}")
            continue

        text = markdown_path.read_text(encoding="utf-8")
        frontmatter = parse_frontmatter(text)
        if frontmatter is None:
            errors.append(f"{relative_path}: missing or unclosed YAML frontmatter")
        else:
            frontmatter_fields = frozenset(frontmatter)
            if frontmatter_fields != EXPECTED_FRONTMATTER_FIELDS:
                missing = sorted(EXPECTED_FRONTMATTER_FIELDS - frontmatter_fields)
                extra = sorted(frontmatter_fields - EXPECTED_FRONTMATTER_FIELDS)
                errors.append(
                    f"{relative_path}: frontmatter field mismatch; missing={missing}, extra={extra}"
                )
            if finding_id is not None and frontmatter.get("id") != str(finding_id):
                errors.append(f"{relative_path}: frontmatter id does not match index id")
            if frontmatter.get("severity") != row.get("severity"):
                errors.append(f"{relative_path}: frontmatter severity does not match index severity")

        headings = re.findall(r"^##\s+(.+?)\s*#*\s*$", text, flags=re.MULTILINE)
        for section in REQUIRED_SECTIONS:
            if section not in headings:
                errors.append(f"{relative_path}: missing '## {section}' section")
        title_match = re.search(r"^#\s+(.+?)\s*$", text, flags=re.MULTILINE)
        if not title_match:
            errors.append(f"{relative_path}: missing title heading")
        elif title_match.group(1) != row.get("title"):
            errors.append(f"{relative_path}: title heading does not match index title")

    findings_dir = dataset / "findings"
    if findings_dir.is_dir():
        for markdown_path in findings_dir.glob("finding-*.md"):
            relative_path = markdown_path.relative_to(dataset).as_posix()
            if relative_path not in indexed_paths:
                errors.append(f"{relative_path}: finding file is not listed in index.jsonl")
    else:
        errors.append(f"missing findings directory: {findings_dir}")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "dataset",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parent / "agent_dataset",
        help="dataset directory (defaults to this repository's agent_dataset)",
    )
    parser.add_argument(
        "--index",
        type=Path,
        help="alternate index to validate against the dataset's existing finding files",
    )
    args = parser.parse_args()
    try:
        errors = validate(args.dataset, args.index)
    except (OSError, UnicodeError) as exc:
        print(f"error: could not read dataset: {exc}", file=sys.stderr)
        return 2
    if errors:
        print(f"Found {len(errors)} structure issue(s):")
        for error in errors:
            print(f"- {error}")
        return 1

    index_path = args.index if args.index is not None else args.dataset / "index.jsonl"
    print(f"Dataset structure is valid: {args.dataset} (index: {index_path})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
