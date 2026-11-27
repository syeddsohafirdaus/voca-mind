import json
from datetime import datetime, timezone

import pytest

from app.knowledge.approval_loader import (
    load_approval_registry,
)


def make_record():
    return {
        "document_id": "synthetic-test",
        "version": "1.0",
        "fingerprint": "a" * 64,
        "reviewer_id": "synthetic-reviewer",
        "approved_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": "APPROVED",
    }


def write_manifest(tmp_path, data):
    path = tmp_path / "approvals.json"
    path.write_text(json.dumps(data))
    return path


def test_empty_manifest(tmp_path):
    path = write_manifest(tmp_path, {
        "schema_version": 1,
        "approvals": [],
    })

    registry = load_approval_registry(path)
    assert registry.get("unknown", "1.0") is None


def test_valid_manifest(tmp_path):
    path = write_manifest(tmp_path, {
        "schema_version": 1,
        "approvals": [make_record()],
    })

    registry = load_approval_registry(path)
    record = registry.get("synthetic-test", "1.0")

    assert record is not None
    assert record.status == "APPROVED"


def test_missing_manifest(tmp_path):
    with pytest.raises(ValueError):
        load_approval_registry(
            tmp_path / "missing.json"
        )


def test_invalid_json(tmp_path):
    path = tmp_path / "approvals.json"
    path.write_text("invalid json")

    with pytest.raises(ValueError):
        load_approval_registry(path)


def test_invalid_schema_version(tmp_path):
    path = write_manifest(tmp_path, {
        "schema_version": 99,
        "approvals": [],
    })

    with pytest.raises(ValueError):
        load_approval_registry(path)


def test_duplicate_approval(tmp_path):
    record = make_record()

    path = write_manifest(tmp_path, {
        "schema_version": 1,
        "approvals": [record, record],
    })

    with pytest.raises(ValueError):
        load_approval_registry(path)


def test_invalid_fingerprint(tmp_path):
    record = make_record()
    record["fingerprint"] = "invalid"

    path = write_manifest(tmp_path, {
        "schema_version": 1,
        "approvals": [record],
    })

    with pytest.raises(ValueError):
        load_approval_registry(path)


def test_revoked_record(tmp_path):
    record = make_record()
    record["status"] = "REVOKED"

    path = write_manifest(tmp_path, {
        "schema_version": 1,
        "approvals": [record],
    })

    registry = load_approval_registry(path)

    assert registry.get(
        "synthetic-test", "1.0"
    ).status == "REVOKED"


def test_invalid_approval_list(tmp_path):
    path = write_manifest(tmp_path, {
        "schema_version": 1,
        "approvals": "invalid",
    })

    with pytest.raises(ValueError):
        load_approval_registry(path)
