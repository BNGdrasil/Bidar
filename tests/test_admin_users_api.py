# --------------------------------------------------------------------------
# Tests for the administrative user management API
#
# Covers the contract Bifrost proxies and the Bantheon admin screens use:
# who may read, who may write, and which conflicts are refused.
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from typing import Any, Dict

import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.crud.auth import create_access_token, get_password_hash
from src.models.users import User


async def _add_user(db: AsyncSession, **kwargs: Any) -> User:
    user = User(**kwargs)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def people(db_session: AsyncSession) -> Dict[str, User]:
    """One super admin, one admin, one plain user and one spare target."""
    created: Dict[str, User] = {}
    definitions = [
        ("super_admin", "boss", "boss@example.com", "super_admin", True),
        ("admin", "manager", "manager@example.com", "admin", False),
        ("user", "plain", "plain@example.com", "user", False),
        ("target", "target", "target@example.com", "user", False),
    ]
    for key, username, email, role, is_superuser in definitions:
        created[key] = await _add_user(
            db_session,
            username=username,
            email=email,
            hashed_password=get_password_hash("adminapipassword123"),
            is_active=True,
            is_superuser=is_superuser,
            role=role,
        )
    return created


def _auth(user: User) -> Dict[str, str]:
    token = create_access_token(
        {"sub": user.username, "user_id": user.id, "role": user.role}
    )
    return {"Authorization": f"Bearer {token}"}


class TestGetUser:
    """GET /users/users/{user_id} is readable from admin upwards."""

    def test_requires_authentication(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """No token means 401."""
        response = client.get(f"/users/users/{people['target'].id}")
        assert response.status_code == 401

    def test_regular_user_forbidden(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """A plain user cannot read another account."""
        response = client.get(
            f"/users/users/{people['target'].id}", headers=_auth(people["user"])
        )
        assert response.status_code == 403
        assert response.json()["detail"] == "Not enough permissions"

    def test_admin_can_read(self, client: TestClient, people: Dict[str, User]) -> None:
        """An admin reads a single account."""
        target = people["target"]
        response = client.get(
            f"/users/users/{target.id}", headers=_auth(people["admin"])
        )
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == target.id
        assert body["username"] == "target"
        assert body["role"] == "user"
        assert body["is_superuser"] is False

    def test_unknown_user_is_404(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """A missing id answers 404 with the default detail shape."""
        response = client.get("/users/users/999999", headers=_auth(people["admin"]))
        assert response.status_code == 404
        assert response.json() == {"detail": "User not found"}


class TestPatchUser:
    """PATCH /users/users/{user_id} is super admin only."""

    def test_requires_authentication(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """No token means 401."""
        response = client.patch(
            f"/users/users/{people['target'].id}", json={"full_name": "New Name"}
        )
        assert response.status_code == 401

    def test_regular_user_forbidden(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """A plain user cannot modify accounts."""
        response = client.patch(
            f"/users/users/{people['target'].id}",
            json={"role": "admin"},
            headers=_auth(people["user"]),
        )
        assert response.status_code == 403

    def test_admin_may_read_but_not_write(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """An admin has read access but cannot change roles."""
        response = client.patch(
            f"/users/users/{people['target'].id}",
            json={"role": "admin"},
            headers=_auth(people["admin"]),
        )
        assert response.status_code == 403

    def test_super_admin_updates_role(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """A super admin promotes a user and is_superuser follows the role."""
        response = client.patch(
            f"/users/users/{people['target'].id}",
            json={"role": "super_admin"},
            headers=_auth(people["super_admin"]),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["role"] == "super_admin"
        assert body["is_superuser"] is True

    def test_super_admin_updates_full_name_only(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """Omitted fields are left untouched instead of being reset."""
        target = people["target"]
        response = client.patch(
            f"/users/users/{target.id}",
            json={"full_name": "Renamed Target"},
            headers=_auth(people["super_admin"]),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["full_name"] == "Renamed Target"
        assert body["role"] == "user"
        assert body["is_active"] is True

    def test_deactivate_through_patch(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """is_active can be set through the same endpoint."""
        response = client.patch(
            f"/users/users/{people['target'].id}",
            json={"is_active": False},
            headers=_auth(people["super_admin"]),
        )
        assert response.status_code == 200
        assert response.json()["is_active"] is False

    def test_unknown_role_is_422(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """A role outside the hierarchy is refused by validation."""
        response = client.patch(
            f"/users/users/{people['target'].id}",
            json={"role": "root"},
            headers=_auth(people["super_admin"]),
        )
        assert response.status_code == 422

    def test_username_is_not_editable(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """Identity fields are rejected rather than silently ignored."""
        response = client.patch(
            f"/users/users/{people['target'].id}",
            json={"username": "hijacked"},
            headers=_auth(people["super_admin"]),
        )
        assert response.status_code == 422

    def test_is_superuser_is_not_editable(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """is_superuser cannot be set directly."""
        response = client.patch(
            f"/users/users/{people['target'].id}",
            json={"is_superuser": True},
            headers=_auth(people["super_admin"]),
        )
        assert response.status_code == 422

    def test_unknown_user_is_404(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """A missing id answers 404."""
        response = client.patch(
            "/users/users/999999",
            json={"full_name": "Nobody"},
            headers=_auth(people["super_admin"]),
        )
        assert response.status_code == 404

    def test_demoting_last_super_admin_is_409(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """The only active super admin cannot demote themselves."""
        response = client.patch(
            f"/users/users/{people['super_admin'].id}",
            json={"role": "admin"},
            headers=_auth(people["super_admin"]),
        )
        assert response.status_code == 409
        assert "super admin" in response.json()["detail"]

    def test_deactivating_last_super_admin_is_409(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """The only active super admin cannot be deactivated."""
        response = client.patch(
            f"/users/users/{people['super_admin'].id}",
            json={"is_active": False},
            headers=_auth(people["super_admin"]),
        )
        assert response.status_code == 409

    async def test_demotion_allowed_with_a_spare_super_admin(
        self,
        client: TestClient,
        db_session: AsyncSession,
        people: Dict[str, User],
    ) -> None:
        """With a second super admin the demotion goes through."""
        spare = await _add_user(
            db_session,
            username="spareboss",
            email="spareboss@example.com",
            hashed_password=get_password_hash("adminapipassword123"),
            is_active=True,
            is_superuser=True,
            role="super_admin",
        )
        response = client.patch(
            f"/users/users/{people['super_admin'].id}",
            json={"role": "admin"},
            headers=_auth(spare),
        )
        assert response.status_code == 200
        assert response.json()["role"] == "admin"
        assert response.json()["is_superuser"] is False


class TestDeleteUser:
    """DELETE /users/users/{user_id} is super admin only."""

    def test_requires_authentication(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """No token means 401."""
        response = client.delete(f"/users/users/{people['target'].id}")
        assert response.status_code == 401

    def test_regular_user_forbidden(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """A plain user cannot delete accounts."""
        response = client.delete(
            f"/users/users/{people['target'].id}", headers=_auth(people["user"])
        )
        assert response.status_code == 403

    def test_admin_forbidden(self, client: TestClient, people: Dict[str, User]) -> None:
        """An admin can read but not delete."""
        response = client.delete(
            f"/users/users/{people['target'].id}", headers=_auth(people["admin"])
        )
        assert response.status_code == 403

    def test_super_admin_deletes(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """A successful delete answers 204 with no body."""
        target_id = people["target"].id
        response = client.delete(
            f"/users/users/{target_id}", headers=_auth(people["super_admin"])
        )
        assert response.status_code == 204
        assert response.content == b""

        follow_up = client.get(
            f"/users/users/{target_id}", headers=_auth(people["super_admin"])
        )
        assert follow_up.status_code == 404

    def test_self_deletion_is_400(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """Deleting your own account is refused."""
        boss = people["super_admin"]
        response = client.delete(f"/users/users/{boss.id}", headers=_auth(boss))
        assert response.status_code == 400
        assert response.json() == {"detail": "You cannot delete your own account"}

    async def test_super_admin_can_delete_another_super_admin(
        self,
        client: TestClient,
        db_session: AsyncSession,
        people: Dict[str, User],
    ) -> None:
        """Deleting a peer is allowed while another active super admin remains."""
        spare = await _add_user(
            db_session,
            username="spareboss",
            email="spareboss@example.com",
            hashed_password=get_password_hash("adminapipassword123"),
            is_active=True,
            is_superuser=True,
            role="super_admin",
        )
        response = client.delete(
            f"/users/users/{spare.id}", headers=_auth(people["super_admin"])
        )
        assert response.status_code == 204

    def test_self_deletion_shields_the_last_super_admin_guard(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """Over HTTP the last super admin is protected by the 400, not the 409.

        The caller of DELETE is always an active super admin, so the target can
        only be the last one when it is the caller, and the self-deletion check
        runs first. The 409 guard in crud.delete_user still protects other
        callers such as the CLI; that path is covered in
        tests/test_security_regressions.py.
        """
        boss = people["super_admin"]
        response = client.delete(f"/users/users/{boss.id}", headers=_auth(boss))
        assert response.status_code == 400

    def test_unknown_user_is_404(
        self, client: TestClient, people: Dict[str, User]
    ) -> None:
        """A missing id answers 404."""
        response = client.delete(
            "/users/users/999999", headers=_auth(people["super_admin"])
        )
        assert response.status_code == 404
