from fastapi.testclient import TestClient

from app.auth.password import hash_password, verify_password
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
            "name": "Integration Test User",
            "email": TEST_EMAIL,
        }

    finally:
        # ------------------------------------------------
        # 7. Always remove the dependency override
        # ------------------------------------------------

        app.dependency_overrides.pop(
            get_db,
            None,
        )


def test_registration_creates_tenant_and_hashed_password(test_db):
    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).post(
            "/api/v1/auth/register",
            json={"name": "New Traveler", "email": "NEW@example.com", "password": "SafePassword123"},
        )
        assert response.status_code == 201
        payload = response.json()
        user = test_db.query(User).filter_by(user_id=payload["user_id"]).one()
        tenant = test_db.query(Tenant).filter_by(tenant_id=payload["tenant_id"]).one()
        assert user.email == "new@example.com"
        assert user.password_hash != "SafePassword123"
        assert verify_password("SafePassword123", user.password_hash)
        assert tenant.tenant_id == user.tenant_id
        assert payload["access_token"]
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_registration_rejects_duplicate_email(test_db):
    create_test_tenant(test_db)
    create_test_user(test_db)

    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).post(
            "/api/v1/auth/register",
            json={"name": "Duplicate", "email": TEST_EMAIL.upper(), "password": "SafePassword123"},
        )
        assert response.status_code == 409
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_registration_validates_email_and_password(test_db):
    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        assert client.post("/api/v1/auth/register", json={"name": "Test", "email": "bad", "password": "SafePassword123"}).status_code == 422
        assert client.post("/api/v1/auth/register", json={"name": "Test", "email": "ok@example.com", "password": "short"}).status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_production_origin_cors_preflight():
    response = TestClient(app).options(
        "/api/v1/auth/login",
        headers={
            "Origin": "https://travel-agentai.netlify.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://travel-agentai.netlify.app"
    assert "POST" in response.headers["access-control-allow-methods"]
