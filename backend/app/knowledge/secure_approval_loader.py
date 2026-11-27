"""Fail-closed loading of signed approval manifests."""

import json
from pathlib import Path

from app.config import settings
from app.knowledge.approval import (
    ApprovalRegistry,
    DocumentApproval,
)
from app.knowledge.approval_loader import DEFAULT_MANIFEST
from app.knowledge.manifest_security import (
    verify_manifest_signature,
)


def load_secure_approval_registry(
    manifest_path: Path | None = None,
    signature_path: Path | None = None,
    public_key: str | None = None,
) -> ApprovalRegistry:

    manifest = Path(
        manifest_path or DEFAULT_MANIFEST
    )

    signature = Path(
        signature_path or
        manifest.with_suffix(".sig")
    )

    key = (
        public_key
        if public_key is not None
        else settings.KNOWLEDGE_APPROVAL_PUBLIC_KEY
    )

    if not key.strip():
        raise ValueError(
            "Trusted approval public key is missing."
        )

    if not manifest.is_file():
        raise ValueError("Approval manifest is missing.")

    if not signature.is_file():
        raise ValueError("Approval signature is missing.")

    manifest_bytes = manifest.read_bytes()

    verify_manifest_signature(
        manifest_bytes,
        signature.read_text(
            encoding="utf-8"
        ).strip(),
        key,
    )

    data = json.loads(manifest_bytes)

    if not isinstance(data, dict):
        raise ValueError("Invalid manifest structure.")

    if data.get("schema_version") != 1:
        raise ValueError("Unsupported manifest version.")

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
            raise ValueError("Duplicate approval record.")

        seen.add(key)
        registry.register(approval)

    return registry
