# --------------------------------------------------------------------------
# Regression tests for SEC-01, SEC-03, SEC-05 and SEC-06
#
# Each test pins a contract that, if it broke again, would hand an attacker an
# administrative account or keep a revoked token usable.
#
# @author bnbong bbbong9@gmail.com
# --------------------------------------------------------------------------
from datetime import timedelta
from typing import Any, Dict

import jwt
import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.crud.auth import (
    ACCESS_TOKEN_TYPE,
    create_access_token,
    create_refresh_token,
    get_password_hash,
)
from src.crud.users import (
    LastSuperAdminError,
    count_active_super_admins,
    create_user,
    deactivate_user,
    delete_user,
    update_user,
)
from src.models.users import User, UserCreate, UserRegisterRequest, UserUpdate

SUPER_ADMIN_PASSWORD = "superadminpassword123"
USER_PASSWORD = "regularpassword123"


async def _add_user(db: AsyncSession, **kwargs: Any) -> User:
    user = User(**kwargs)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def accounts(db_session: AsyncSession) -> Dict[str, User]:
    """Create one super admin and one regular user."""
    super_admin = await _add_user(
        db_session,
        username="root",
        email="root@example.com",
        hashed_password=get_password_hash(SUPER_ADMIN_PASSWORD),
        is_active=True,
        is_superuser=True,
        role="super_admin",
    )
    regular = await _add_user(
        db_session,
        username="plain",
        email="plain@example.com",
        hashed_password=get_password_hash(USER_PASSWORD),
        is_active=True,
        is_superuser=False,
        role="user",
    )
    return {"super_admin": super_admin, "user": regular}


def _access_token(user: User, **overrides: Any) -> str:
    payload: Dict[str, Any] = {
        "sub": user.username,
        "user_id": user.id,
        "role": user.role,
    }
    payload.update(overrides)
    return create_access_token(payload)


def _auth(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestClosedRegistration:
    """SEC-01: no unauthenticated path can create a privileged account."""

    def test_register_endpoint_is_gone(self, client: TestClient) -> None:
        """The public registration route no longer exists."""
        response = client.post(
            "/users/register",
            json={
                "username": "attacker",
                "email": "attacker@example.com",
                "password": "attackerpassword",
                "role": "super_admin",
                "is_superuser": True,
            },
        )
        assert response.status_code == 404

    def test_admin_create_requires_authentication(self, client: TestClient) -> None:
        """POST /users without a token is refused."""
        response = client.post(
            "/users",
            json={
                "username": "attacker",
                "email": "attacker@example.com",
                "password": "attackerpassword",
            },
        )
        assert response.status_code == 401

    def test_regular_user_cannot_create_accounts(
        self, client: TestClient, accounts: Dict[str, User]
    ) -> None:
        """A normal user token gets 403 on the admin creation endpoint."""
        token = _access_token(accounts["user"])
        response = client.post(
            "/users",
            json={
                "username": "attacker",
                "email": "attacker@example.com",
                "password": "attackerpassword",
                "role": "super_admin",
            },
            headers=_auth(token),
        )
        assert response.status_code == 403

    def test_super_admin_can_create_account(
        self, client: TestClient, accounts: Dict[str, User]
    ) -> None:
        """A super admin creates accounts and may set the role."""
        token = _access_token(accounts["super_admin"])
        response = client.post(
            "/users",
            json={
                "username": "newmod",
                "email": "newmod@example.com",
                "password": "newmodpassword123",
                "role": "moderator",
            },
            headers=_auth(token),
        )
        assert response.status_code == 201
        body = response.json()
        assert body["role"] == "moderator"
        assert body["is_superuser"] is False

    def test_public_schema_rejects_privileged_fields(self) -> None:
        """The reserved public signup schema refuses privileged fields."""
        with pytest.raises(ValidationError):
            UserRegisterRequest(
                username="attacker",
                email="attacker@example.com",
                password="attackerpassword",
                role="super_admin",  # type: ignore[call-arg]
            )

    async def test_is_superuser_is_derived_from_role(
        self, db_session: AsyncSession, accounts: Dict[str, User]
    ) -> None:
        """is_superuser follows role and cannot be set independently."""
        created = await create_user(
            db_session,
            UserCreate(
                username="derived",
                email="derived@example.com",
                password="derivedpassword123",
                role="super_admin",
            ),
        )
        assert created.is_superuser is True

        demoted = await update_user(
            db_session, int(created.id or 0), UserUpdate(role="admin")
        )
        assert demoted is not None
        assert demoted.is_superuser is False

    async def test_invalid_role_is_rejected(self) -> None:
        """An unknown role cannot be persisted through the admin schema."""
        with pytest.raises(ValidationError):
            UserCreate(
                username="weird",
                email="weird@example.com",
                password="weirdpassword123",
                role="root",
            )


class TestAdminEndpointAuthorization:
    """SEC-01/SEC-03: management endpoints need a current admin role."""

    def test_list_users_rejects_regular_user(
        self, client: TestClient, accounts: Dict[str, User]
    ) -> None:
        """A normal user token cannot list accounts."""
        response = client.get(
            "/users/users", headers=_auth(_access_token(accounts["user"]))
        )
        assert response.status_code == 403

    def test_list_users_allows_super_admin(
        self, client: TestClient, accounts: Dict[str, User]
    ) -> None:
        """A super admin token lists accounts."""
        response = client.get(
            "/users/users", headers=_auth(_access_token(accounts["super_admin"]))
        )
        assert response.status_code == 200
        assert len(response.json()) >= 2

    def test_forged_role_claim_does_not_grant_access(
        self, client: TestClient, accounts: Dict[str, User]
    ) -> None:
        """A correctly signed token with an inflated role claim is ignored."""
        token = _access_token(accounts["user"], role="super_admin")
        response = client.get("/users/users", headers=_auth(token))
        assert response.status_code == 403


class TestTokenHandling:
    """SEC-03: token type, claims, expiry and account state are enforced."""

    def test_refresh_token_rejected_as_bearer(
        self, client: TestClient, accounts: Dict[str, User]
    ) -> None:
        """A refresh token presented as a Bearer access token gives 401."""
        admin = accounts["super_admin"]
        refresh = create_refresh_token(
            {"sub": admin.username, "user_id": admin.id, "role": admin.role}
        )
        response = client.get("/auth/me", headers=_auth(refresh))
        assert response.status_code == 401

    def test_rbac_rejects_refresh_token(
        self, client: TestClient, accounts: Dict[str, User]
    ) -> None:
        """/rbac/verify-permission only accepts access tokens."""
        admin = accounts["super_admin"]
        refresh = create_refresh_token(
            {"sub": admin.username, "user_id": admin.id, "role": admin.role}
        )
        response = client.post(
            "/rbac/verify-permission",
            json={"required_role": "super_admin"},
            headers=_auth(refresh),
        )
        assert response.status_code == 401

    def test_rbac_accepts_access_token(
        self, client: TestClient, accounts: Dict[str, User]
    ) -> None:
        """The response contract used by Bifrost is unchanged."""
        response = client.post(
            "/rbac/verify-permission",
            json={"required_role": "admin"},
            headers=_auth(_access_token(accounts["super_admin"])),
        )
        assert response.status_code == 200
        body = response.json()
        assert body == {
            "allowed": True,
            "user_id": accounts["super_admin"].id,
            "username": "root",
            "role": "super_admin",
        }

    async def test_rbac_rejects_demoted_user_existing_token(
        self,
        client: TestClient,
        db_session: AsyncSession,
        accounts: Dict[str, User],
    ) -> None:
        """A token issued before a demotion loses its privileges."""
        admin = await _add_user(
            db_session,
            username="secondadmin",
            email="secondadmin@example.com",
            hashed_password=get_password_hash("secondadminpassword"),
            is_active=True,
            is_superuser=True,
            role="super_admin",
        )
        token = _access_token(admin)

        allowed = client.post(
            "/rbac/verify-permission",
            json={"required_role": "super_admin"},
            headers=_auth(token),
        )
        assert allowed.status_code == 200

        await update_user(db_session, int(admin.id or 0), UserUpdate(role="user"))

        denied = client.post(
            "/rbac/verify-permission",
            json={"required_role": "super_admin"},
            headers=_auth(token),
        )
        assert denied.status_code == 403

    async def test_rbac_rejects_deactivated_user(
        self,
        client: TestClient,
        db_session: AsyncSession,
        accounts: Dict[str, User],
    ) -> None:
        """A deactivated account loses access with its existing token."""
        user = accounts["user"]
        token = _access_token(user)

        await deactivate_user(db_session, int(user.id or 0))

        response = client.post(
            "/rbac/verify-permission",
            json={"required_role": "user"},
            headers=_auth(token),
        )
        assert response.status_code == 401

    def test_expired_token_rejected(
        self, client: TestClient, accounts: Dict[str, User]
    ) -> None:
        """An expired access token is refused."""
        token = create_access_token(
            {
                "sub": accounts["user"].username,
                "user_id": accounts["user"].id,
                "role": "user",
            },
            expires_delta=timedelta(seconds=-10),
        )
        response = client.get("/auth/me", headers=_auth(token))
        assert response.status_code == 401

    def test_bad_signature_rejected(
        self, client: TestClient, accounts: Dict[str, User]
    ) -> None:
        """A token signed with another key is refused."""
        token = jwt.encode(
            {
                "sub": accounts["user"].username,
                "user_id": accounts["user"].id,
                "role": "user",
                "type": ACCESS_TOKEN_TYPE,
                "exp": 4102444800,
            },
            "a-completely-different-signing-key-value",
            algorithm=settings.JWT_ALGORITHM,
        )
        response = client.get("/auth/me", headers=_auth(token))
        assert response.status_code == 401

    def test_missing_claims_rejected(
        self, client: TestClient, accounts: Dict[str, User]
    ) -> None:
        """A token without user_id is refused even if correctly signed."""
        token = create_access_token({"sub": accounts["user"].username})
        response = client.get("/auth/me", headers=_auth(token))
        assert response.status_code == 401

    def test_subject_mismatch_rejected(
        self, client: TestClient, accounts: Dict[str, User]
    ) -> None:
        """user_id and sub must refer to the same account."""
        token = create_access_token(
            {
                "sub": accounts["user"].username,
                "user_id": accounts["super_admin"].id,
                "role": "super_admin",
            }
        )
        response = client.get("/auth/me", headers=_auth(token))
        assert response.status_code == 401

    def test_access_token_claims_are_utc_aware(self, accounts: Dict[str, User]) -> None:
        """Iat and exp are issued from an aware UTC clock."""
        token = _access_token(accounts["user"])
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        assert payload["type"] == ACCESS_TOKEN_TYPE
        assert payload["exp"] > payload["iat"]


class TestInactiveAccountTokenIssuance:
    """SEC-03: inactive accounts get no new tokens."""

    async def test_login_rejects_inactive_account(
        self,
        client: TestClient,
        db_session: AsyncSession,
        accounts: Dict[str, User],
    ) -> None:
        """A deactivated user cannot obtain a token pair."""
        user = accounts["user"]
        await deactivate_user(db_session, int(user.id or 0))

        response = client.post(
            "/auth/token",
            data={"username": user.username, "password": USER_PASSWORD},
        )
        assert response.status_code == 401

    async def test_refresh_rejects_inactive_account(
        self,
        client: TestClient,
        db_session: AsyncSession,
        accounts: Dict[str, User],
    ) -> None:
        """A refresh token stops working once the account is deactivated."""
        user = accounts["user"]
        login = client.post(
            "/auth/token",
            data={"username": user.username, "password": USER_PASSWORD},
        )
        assert login.status_code == 200
        refresh_token = login.json()["refresh_token"]

        await deactivate_user(db_session, int(user.id or 0))

        response = client.post("/auth/refresh", json={"refresh_token": refresh_token})
        assert response.status_code == 401

    def test_refresh_rejects_access_token(
        self, client: TestClient, accounts: Dict[str, User]
    ) -> None:
        """An access token cannot be swapped in for a refresh token."""
        response = client.post(
            "/auth/refresh",
            json={"refresh_token": _access_token(accounts["user"])},
        )
        assert response.status_code == 401


class TestLastSuperAdminProtection:
    """The system always keeps at least one active super admin."""

    async def test_deactivate_last_super_admin_refused(
        self, db_session: AsyncSession, accounts: Dict[str, User]
    ) -> None:
        """Deactivating the only super admin raises."""
        assert await count_active_super_admins(db_session) == 1
        with pytest.raises(LastSuperAdminError):
            await deactivate_user(db_session, int(accounts["super_admin"].id or 0))

    async def test_demote_last_super_admin_refused(
        self, db_session: AsyncSession, accounts: Dict[str, User]
    ) -> None:
        """Demoting the only super admin raises."""
        with pytest.raises(LastSuperAdminError):
            await update_user(
                db_session,
                int(accounts["super_admin"].id or 0),
                UserUpdate(role="admin"),
            )

    async def test_delete_last_super_admin_refused(
        self, db_session: AsyncSession, accounts: Dict[str, User]
    ) -> None:
        """Deleting the only super admin raises."""
        with pytest.raises(LastSuperAdminError):
            await delete_user(db_session, int(accounts["super_admin"].id or 0))

    async def test_second_super_admin_allows_demotion(
        self, db_session: AsyncSession, accounts: Dict[str, User]
    ) -> None:
        """With a spare super admin the operation succeeds."""
        await _add_user(
            db_session,
            username="backupadmin",
            email="backupadmin@example.com",
            hashed_password=get_password_hash("backupadminpassword"),
            is_active=True,
            is_superuser=True,
            role="super_admin",
        )
        demoted = await update_user(
            db_session,
            int(accounts["super_admin"].id or 0),
            UserUpdate(role="admin"),
        )
        assert demoted is not None
        assert demoted.role == "admin"

    def test_self_deactivation_shields_the_guard_over_http(
        self, client: TestClient, accounts: Dict[str, User]
    ) -> None:
        """Over HTTP the last super admin is protected by the 400, not the 409.

        Deactivating yourself is refused first, and a caller who is not the
        target is always another active super admin, so the target can never
        be the last one. The 409 guard in crud.deactivate_user still protects
        the CLI and any other non-HTTP caller; that path is covered by
        test_deactivate_last_super_admin_refused above.
        """
        response = client.put(
            f"/users/users/{accounts['super_admin'].id}/deactivate",
            headers=_auth(_access_token(accounts["super_admin"])),
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "You cannot deactivate your own account"}


class TestLoginRateLimit:
    """SEC-06: repeated login attempts are slowed down in process."""

    def test_login_attempts_are_limited(
        self, client: TestClient, accounts: Dict[str, User]
    ) -> None:
        """Beyond the per-minute limit the endpoint answers 429."""
        limit = settings.LOGIN_RATE_LIMIT_PER_MINUTE
        statuses = [
            client.post(
                "/auth/token",
                data={"username": "plain", "password": "wrong-password"},
            ).status_code
            for _ in range(limit + 2)
        ]
        assert statuses[0] == 401
        assert statuses[-1] == 429

    def test_health_and_metrics_are_not_limited(self, client: TestClient) -> None:
        """Operational endpoints stay outside the limiter."""
        for _ in range(settings.LOGIN_RATE_LIMIT_PER_MINUTE + 5):
            assert client.get("/health").status_code == 200
        assert client.get("/metrics").status_code == 200
