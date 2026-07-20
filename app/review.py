"""Apply critical-review checklist status to a saved assessment payload."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

VALID_REVIEW_STATUSES = frozenset({
    "draft",
    "reviewed_pending_external",
    "reviewed_external_complete",
    "internal_only",
})

_ISO_VERSION = {
    "draft": "1.0 (draft, pending independent critical review)",
    "reviewed_pending_external": "1.0 (reviewed — pending external panel sign-off)",
    "reviewed_external_complete": "1.0 (externally reviewed)",
    "internal_only": "1.0 (internal use only)",
}

_CONFORMANCE = {
    "draft": (
        "This is a finished, ISO-based draft. It still needs an independent critical review "
        "before it can be shared publicly."
    ),
    "reviewed_pending_external": (
        "Internal critical-review checklist is complete. An independent external panel review "
        "is still required before public release."
    ),
    "reviewed_external_complete": (
        "This study has completed independent external critical review and may be shared publicly."
    ),
    "internal_only": (
        "This is an ISO-based report for internal use, and no external critical review is required."
    ),
}


def apply_review_status(payload: dict[str, Any], status: str) -> dict[str, Any]:
    """Return a copy of payload with review_status and ISO document_control updates."""
    if status not in VALID_REVIEW_STATUSES:
        raise ValueError(f"Invalid review_status: {status}")

    out = deepcopy(payload)
    out["review_status"] = status
    iso = dict(out.get("iso_report") or {})
    doc = dict(iso.get("document_control") or {})
    doc["review_status"] = status
    doc["version"] = _ISO_VERSION[status]
    iso["document_control"] = doc
    iso["conformance_status"] = _CONFORMANCE[status]

    interp = dict(iso.get("interpretation") or {})
    if status == "reviewed_pending_external":
        interp["public_disclosure"] = (
            "Internal review is complete and the report is ready for independent external "
            "critical review. Until the external panel signs off, treat this as "
            "reviewed-pending-external rather than a published public claim."
        )
    elif status == "reviewed_external_complete":
        interp["public_disclosure"] = (
            "External critical review is complete. The report may be shared publicly as an "
            "ISO-conformant environmental claim."
        )
    elif status == "internal_only":
        interp["public_disclosure"] = (
            "This report is for the farm's own use and is not meant to be shared publicly."
        )
    else:
        interp["public_disclosure"] = (
            "This report is written so it can be shared outside the farm. Before it is published, "
            "the results need to pass an independent critical review. Until that review is complete, "
            "the report should be treated as a finished draft rather than a reviewed public claim."
        )
    iso["interpretation"] = interp

    cr = dict(iso.get("critical_review") or {})
    if status == "reviewed_pending_external":
        cr["required"] = True
        cr["status"] = "Internal review complete; external panel review pending."
    elif status == "reviewed_external_complete":
        cr["required"] = True
        cr["status"] = "External independent critical review complete."
    elif status == "internal_only":
        cr["required"] = False
        cr["status"] = "Not required, as the study is for internal use only."
    else:
        cr["required"] = True
        cr["status"] = "Required, and still to be done. The report is a finished draft, ready for review."
    iso["critical_review"] = cr
    out["iso_report"] = iso
    return out
