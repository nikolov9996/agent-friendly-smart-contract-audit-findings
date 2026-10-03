"""Source-label normalization for the audit finding index.

These mappings standardize reported labels; they do not reassess findings.
The reported severity must be retained separately from the derived metadata.
"""

from __future__ import annotations


CANONICAL_SEVERITIES = ("Critical", "High", "Medium", "Low", "Informational")
_SINGLE_LABELS = {
    "critical": "Critical",
    "critical risk": "Critical",
    "high": "High",
    "high risk": "High",
    "medium": "Medium",
    "medium risk": "Medium",
    "low": "Low",
    "low risk": "Low",
    "informational": "Informational",
    "info": "Informational",
}
_COMBINED_LABELS = {
    "crit/high": ("Critical", "High"),
    "low/info": ("Low", "Informational"),
}


def normalize_severity(label: str) -> tuple[str | None, list[str]]:
    """Return a canonical tier and candidates without guessing unknown labels.

    Matching ignores surrounding whitespace and case. Candidate order follows
    the policy, and each call returns a new list.
    """
    if not isinstance(label, str) or not label.strip():
        raise ValueError("severity must be a non-empty string")
    key = label.strip().casefold()
    normalized = _SINGLE_LABELS.get(key)
    if normalized is not None:
        return normalized, [normalized]
    return None, list(_COMBINED_LABELS.get(key, ()))


def severity_metadata_errors(row: dict[str, object]) -> list[str]:
    """Check derived fields against the reported label and the shared policy."""
    errors: list[str] = []
    normalized = row.get("severity_normalized")
    candidates = row.get("severity_candidates")

    if normalized is not None and (
        not isinstance(normalized, str) or normalized not in CANONICAL_SEVERITIES
    ):
        errors.append("severity_normalized must be a canonical severity or null")
    if not isinstance(candidates, list):
        errors.append("severity_candidates must be a list")
    elif any(
        not isinstance(candidate, str) or candidate not in CANONICAL_SEVERITIES
        for candidate in candidates
    ):
        errors.append("severity_candidates must contain only canonical severities")
    elif len(candidates) != len(set(candidates)):
        errors.append("severity_candidates must not contain duplicates")

    label = row.get("severity")
    if isinstance(label, str) and label.strip():
        expected_normalized, expected_candidates = normalize_severity(label)
        if normalized != expected_normalized:
            errors.append(
                f"severity_normalized must be {expected_normalized!r} "
                f"for reported severity {label!r}"
            )
        if candidates != expected_candidates:
            errors.append(
                f"severity_candidates must be {expected_candidates!r} "
                f"for reported severity {label!r}"
            )
    return errors
