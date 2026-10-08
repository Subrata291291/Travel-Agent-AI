from fastapi.testclient import TestClient

from app.auth.password import hash_password
from app.database.connection import get_db
from app.database.models import Tenant, User
from app.main import app


TEST_TENANT_ID = "integration_test_tenant"
TEST_USER_ID = "integration_test_user"
TEST_EMAIL = "integration@example.com"
TEST_PASSWORD = "TestPassword123!"


def create_test_tenant(db):
    """
    Create a tenant inside the isolated integration database.
    """

    tenant = Tenant(
        tenant_id=TEST_TENANT_ID,
        name="Integration Test Tenant",
        slug="integration-test-tenant",
        status="active",
    )

    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    return tenant


def create_test_user(db):
    """
    Create an active test user with a bcrypt password hash.
    """

    user = User(
        user_id=TEST_USER_ID,
        tenant_id=TEST_TENANT_ID,
        email=TEST_EMAIL,
        password_hash=hash_password(TEST_PASSWORD),
        name="Integration Test User",
        role="user",
        status="active",
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def test_login_and_current_user(test_db):
    """
    Verify the complete authentication flow.

    Flow:

        Test database
            ↓
        Create tenant
            ↓
        Create user
            ↓
        POST /api/v1/auth/login
            ↓
        Receive JWT
            ↓
        GET /api/v1/auth/me
            ↓
        Verify authenticated identity
    """

    # ----------------------------------------------------
    # 1. Create test data
    # ----------------------------------------------------

    create_test_tenant(test_db)
    create_test_user(test_db)

    # ----------------------------------------------------
    # 2. Replace the production database dependency
    #    with the isolated test database.
    # ----------------------------------------------------

    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    try:
        client = TestClient(app)

        # ------------------------------------------------
        # 3. Login
        # ------------------------------------------------

        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": TEST_EMAIL,
                "password": TEST_PASSWORD,
            },
        )

        assert login_response.status_code == 200

        login_data = login_response.json()

        assert login_data["token_type"] == "bearer"
        assert login_data["user_id"] == TEST_USER_ID
        assert login_data["tenant_id"] == TEST_TENANT_ID
        assert login_data["role"] == "user"

        assert login_data["access_token"]

        # ------------------------------------------------
        # 4. Use the returned JWT
        # ------------------------------------------------

        access_token = login_data["access_token"]

        auth_headers = {
            "Authorization": f"Bearer {access_token}",
        }

        # ------------------------------------------------
        # 5. Call /auth/me
        # ------------------------------------------------

        me_response = client.get(
            "/api/v1/auth/me",
            headers=auth_headers,
        )

        assert me_response.status_code == 200

        me_data = me_response.json()

        # ------------------------------------------------
        # 6. Verify authenticated identity
        # ------------------------------------------------

        assert me_data == {
            "user_id": TEST_USER_ID,
            "tenant_id": TEST_TENANT_ID,
            "role": "user",
        }

    finally:
        # ------------------------------------------------
        # 7. Always remove the dependency override
        # ------------------------------------------------

        app.dependency_overrides.pop(
            get_db,
            None,
        )