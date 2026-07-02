"""Shared pytest fixtures.

Configures an isolated SQLite test database (a temp file so all async
connections share schema + data), seeds one user per role, and exposes an
``httpx`` client plus role-scoped auth headers.
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

# Configure the environment BEFORE importing application modules so that
# ``get_settings`` (lru-cached) reads the test values.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEST_DB = Path(__file__).resolve().parent / "_test.db"

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB.as_posix()}"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["JWT_SECRET_KEY"] = "test-secret-key"
os.environ["LOGS_DIR"] = str(Path(__file__).resolve().parent / "_logs")
os.environ["SCREENSHOTS_DIR"] = str(Path(__file__).resolve().parent / "_shots")
os.environ["LIVE_FRAMES_DIR"] = str(Path(__file__).resolve().parent / "_live")
os.environ["UPLOADS_DIR"] = str(Path(__file__).resolve().parent / "_uploads")

# Make the standalone ai-repo importable for detection-logic unit tests.
sys.path.insert(0, str(_REPO_ROOT / "ai-repo"))

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from app.core.database import AsyncSessionLocal, engine  # noqa: E402
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.enums import Role  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base, User  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

_PASSWORD = "Passw0rd!"


@pytest_asyncio.fixture
async def _database():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def users(_database) -> dict[str, dict]:
    records = {
        "super": ("super@example.com", Role.SUPER_ADMIN),
        "admin": ("admin@example.com", Role.ADMIN),
        "viewer": ("viewer@example.com", Role.VIEWER),
    }
    created: dict[str, dict] = {}
    async with AsyncSessionLocal() as session:
        for key, (email, role) in records.items():
            user = User(
                user_id=uuid.uuid4(),
                name=key.title(),
                email=email,
                password_hash=hash_password(_PASSWORD),
                role=role,
                is_active=True,
            )
            session.add(user)
            created[key] = {"id": user.user_id, "email": email, "role": role}
        await session.commit()
    return created


@pytest.fixture
def password() -> str:
    return _PASSWORD


@pytest.fixture
def token_for(users):
    def _make(role_key: str) -> dict[str, str]:
        record = users[role_key]
        token = create_access_token(
            str(record["id"]),
            extra_claims={"role": record["role"].value, "email": record["email"]},
        )
        return {"Authorization": f"Bearer {token}"}

    return _make


@pytest_asyncio.fixture
async def client(_database) -> AsyncClient:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


def pytest_sessionfinish(session, exitstatus):
    if _TEST_DB.exists():
        _TEST_DB.unlink()
