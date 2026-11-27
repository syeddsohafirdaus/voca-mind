"""Platform administrator authorization tests."""

import pytest
from fastapi import HTTPException

from app.auth.admin import (
    get_admin_uids,
    require_platform_admin,
)
from app.config import settings


def test_empty_admin_configuration(monkeypatch):
    monkeypatch.setattr(
        settings, "PLATFORM_ADMIN_UIDS", ""
    )
    assert get_admin_uids() == frozenset()


def test_multiple_admin_uids(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "admin-one, admin-two, admin-one, ",
    )
    assert get_admin_uids() == {
        "admin-one",
        "admin-two",
    }


@pytest.mark.asyncio
async def test_authorized_admin(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "trusted-admin",
    )

    result = await require_platform_admin(
        "trusted-admin"
    )

    assert result == "trusted-admin"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "uid",
    [
        "ordinary-client",
        "ordinary-doctor",
        "ordinary-guardian",
        "trusted-admin-fake",
        "TRUSTED-ADMIN",
        "",
    ],
)
async def test_unauthorized_admin(monkeypatch, uid):
    monkeypatch.setattr(
        settings,
        "PLATFORM_ADMIN_UIDS",
        "trusted-admin",
    )

    with pytest.raises(HTTPException) as exc:
        await require_platform_admin(uid)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_access_disabled_by_default(monkeypatch):
    monkeypatch.setattr(
        settings, "PLATFORM_ADMIN_UIDS", ""
    )

    with pytest.raises(HTTPException) as exc:
        await require_platform_admin("any-user")

    assert exc.value.status_code == 403
