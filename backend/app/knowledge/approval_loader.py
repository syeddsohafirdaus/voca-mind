"""Load document approval records from a controlled manifest."""

import json
from pathlib import Path

from app.knowledge.approval import (
    ApprovalRegistry,
    DocumentApproval,
)

DEFAULT_MANIFEST = (
    Path(__file__).resolve().parent
    / "data"
    / "approvals.json"
)


def load_approval_registry(
    path: Path | None = None,
) -> ApprovalRegistry:

    manifest = Path(path or DEFAULT_MANIFEST)

    if not manifest.is_file():
        raise ValueError("Approval manifest is missing.")

    data = json.loads(
        manifest.read_text(encoding="utf-8")
    )

    if data.get("schema_version") != 1:
        raise ValueError(
            "Unsupported approval manifest version."
        )

    records = data.get("approvals")

    if not isinstance(records, list):
        raise ValueError("Invalid approval records.")

    registry = ApprovalRegistry()
    seen = set()

    for record in records:
        approval = DocumentApproval.model_validate(
            record
        )

        key = (
            approval.document_id,
            approval.version,
        )

        if key in seen:
            raise ValueError(
                "Duplicate document approval record."
            )

        seen.add(key)
        registry.register(approval)

    return registry
