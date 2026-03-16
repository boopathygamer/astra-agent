"""
JWT Authentication & Multi-User Support
════════════════════════════════════════
Production-grade authentication with JWT tokens, user profiles,
per-user knowledge isolation, and role-based access control.

Capabilities:
  1. JWT Token Management  — Issue, verify, refresh tokens
  2. User Profiles         — Individual settings & preferences
  3. Role-Based Access     — Admin, user, viewer roles
  4. API Key Auth          — Backward compatible with X-API-Key
  5. Session Binding       — Link auth sessions to agent sessions
  6. Rate Limiting Per User — User-specific quotas
"""

import hashlib
import hmac
import json
import logging
import os
import time
import base64
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class UserRole(Enum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


@dataclass
class UserProfile:
    """A system user."""
    user_id: str = ""
    username: str = ""
    email: str = ""
    role: UserRole = UserRole.USER
    hashed_password: str = ""
    preferences: Dict[str, Any] = field(default_factory=dict)
    api_key: str = ""
    created_at: float = field(default_factory=time.time)
    last_login: float = 0.0
    is_active: bool = True
    session_ids: List[str] = field(default_factory=list)
    rate_limit: int = 100  # requests per minute
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.user_id:
            self.user_id = hashlib.md5(
                f"{self.username}_{self.created_at}".encode()
            ).hexdigest()[:12]
        if not self.api_key:
            self.api_key = hashlib.sha256(
                f"{self.user_id}_{os.urandom(16).hex()}".encode()
            ).hexdigest()[:32]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "preferences": self.preferences,
        }


@dataclass
class JWTPayload:
    """JWT token payload."""
    user_id: str = ""
    username: str = ""
    role: str = "user"
    issued_at: float = field(default_factory=time.time)
    expires_at: float = 0.0
    token_type: str = "access"  # access or refresh

    def __post_init__(self):
        if self.expires_at == 0:
            if self.token_type == "access":
                self.expires_at = self.issued_at + 3600  # 1 hour
            else:
                self.expires_at = self.issued_at + 86400 * 7  # 7 days

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at


class AuthManager:
    """
    JWT authentication and multi-user management system.
    """

    def __init__(self, secret_key: str = None, data_dir: Optional[str] = None):
        self._secret = secret_key or os.getenv("AUTH_SECRET_KEY", "astra-agent-secret-key-change-in-prod")
        self.data_dir = Path(data_dir) if data_dir else Path("data/auth")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._users: Dict[str, UserProfile] = {}
        self._api_key_index: Dict[str, str] = {}  # api_key → user_id
        self._revoked_tokens: set = set()

        self._load()

        # Create default admin if no users exist
        if not self._users:
            self.create_user("admin", "admin@astra.local", "admin", UserRole.ADMIN)

        logger.info(f"[AUTH] Manager initialized: {len(self._users)} users")

    # ── Password Hashing ──

    @staticmethod
    def _hash_password(password: str, salt: str = "") -> str:
        if not salt:
            salt = os.urandom(16).hex()
        hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return f"{salt}${hashed.hex()}"

    @staticmethod
    def _verify_password(password: str, hashed: str) -> bool:
        parts = hashed.split("$")
        if len(parts) != 2:
            return False
        salt, expected = parts
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
        return hmac.compare_digest(actual.hex(), expected)

    # ── User Management ──

    def create_user(self, username: str, email: str = "",
                    password: str = "", role: UserRole = UserRole.USER) -> UserProfile:
        """Create a new user."""
        # Check for duplicate username
        for u in self._users.values():
            if u.username == username:
                raise ValueError(f"Username '{username}' already exists")

        user = UserProfile(
            username=username, email=email,
            role=role,
            hashed_password=self._hash_password(password) if password else "",
        )
        self._users[user.user_id] = user
        self._api_key_index[user.api_key] = user.user_id
        self._save()
        logger.info(f"[AUTH] User created: {username} ({role.value})")
        return user

    def authenticate(self, username: str, password: str) -> Optional[UserProfile]:
        """Authenticate a user by username/password."""
        for user in self._users.values():
            if user.username == username and user.is_active:
                if self._verify_password(password, user.hashed_password):
                    user.last_login = time.time()
                    self._save()
                    return user
        return None

    def authenticate_api_key(self, api_key: str) -> Optional[UserProfile]:
        """Authenticate by API key."""
        user_id = self._api_key_index.get(api_key)
        if user_id:
            user = self._users.get(user_id)
            if user and user.is_active:
                return user
        return None

    def get_user(self, user_id: str) -> Optional[UserProfile]:
        return self._users.get(user_id)

    def list_users(self) -> List[Dict]:
        return [u.to_dict() for u in self._users.values()]

    def update_preferences(self, user_id: str, preferences: Dict) -> bool:
        user = self._users.get(user_id)
        if user:
            user.preferences.update(preferences)
            self._save()
            return True
        return False

    # ── JWT Operations ──

    def generate_token(self, user: UserProfile, token_type: str = "access") -> str:
        """Generate a JWT token."""
        payload = JWTPayload(
            user_id=user.user_id,
            username=user.username,
            role=user.role.value,
            token_type=token_type,
        )
        return self._encode_jwt(payload)

    def verify_token(self, token: str) -> Optional[JWTPayload]:
        """Verify and decode a JWT token."""
        if token in self._revoked_tokens:
            return None
        return self._decode_jwt(token)

    def revoke_token(self, token: str) -> None:
        self._revoked_tokens.add(token)

    def refresh_token(self, refresh_token: str) -> Optional[str]:
        """Use a refresh token to get a new access token."""
        payload = self.verify_token(refresh_token)
        if not payload or payload.token_type != "refresh":
            return None
        user = self._users.get(payload.user_id)
        if not user:
            return None
        return self.generate_token(user, "access")

    def _encode_jwt(self, payload: JWTPayload) -> str:
        """Simple JWT encoding (no external deps)."""
        header = base64.urlsafe_b64encode(
            json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
        ).rstrip(b"=").decode()

        body = base64.urlsafe_b64encode(
            json.dumps({
                "user_id": payload.user_id,
                "username": payload.username,
                "role": payload.role,
                "iat": payload.issued_at,
                "exp": payload.expires_at,
                "type": payload.token_type,
            }).encode()
        ).rstrip(b"=").decode()

        signature = hmac.new(
            self._secret.encode(), f"{header}.{body}".encode(), "sha256"
        ).hexdigest()

        return f"{header}.{body}.{signature}"

    def _decode_jwt(self, token: str) -> Optional[JWTPayload]:
        """Decode and verify a JWT."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return None

            header, body, signature = parts

            # Verify signature
            expected_sig = hmac.new(
                self._secret.encode(), f"{header}.{body}".encode(), "sha256"
            ).hexdigest()

            if not hmac.compare_digest(signature, expected_sig):
                return None

            # Decode body
            padded = body + "=" * (4 - len(body) % 4)
            data = json.loads(base64.urlsafe_b64decode(padded))

            payload = JWTPayload(
                user_id=data["user_id"],
                username=data["username"],
                role=data["role"],
                issued_at=data["iat"],
                expires_at=data["exp"],
                token_type=data.get("type", "access"),
            )

            if payload.is_expired:
                return None
            return payload

        except Exception as e:
            logger.warning(f"[AUTH] JWT decode failed: {e}")
            return None

    # ── Role Checks ──

    def has_permission(self, user_id: str, required_role: UserRole) -> bool:
        user = self._users.get(user_id)
        if not user:
            return False
        role_hierarchy = {UserRole.ADMIN: 3, UserRole.USER: 2, UserRole.VIEWER: 1}
        return role_hierarchy.get(user.role, 0) >= role_hierarchy.get(required_role, 0)

    # ── Persistence ──

    def _save(self) -> None:
        path = self.data_dir / "users.json"
        try:
            data = {
                uid: {
                    "username": u.username, "email": u.email,
                    "role": u.role.value, "hashed_password": u.hashed_password,
                    "api_key": u.api_key, "is_active": u.is_active,
                    "created_at": u.created_at, "last_login": u.last_login,
                    "preferences": u.preferences, "rate_limit": u.rate_limit,
                }
                for uid, u in self._users.items()
            }
            path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            logger.error(f"[AUTH] Save failed: {e}")

    def _load(self) -> None:
        path = self.data_dir / "users.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            for uid, ud in data.items():
                user = UserProfile(
                    username=ud["username"], email=ud.get("email", ""),
                    role=UserRole(ud.get("role", "user")),
                    hashed_password=ud.get("hashed_password", ""),
                    api_key=ud.get("api_key", ""),
                    is_active=ud.get("is_active", True),
                    rate_limit=ud.get("rate_limit", 100),
                    preferences=ud.get("preferences", {}),
                )
                user.user_id = uid
                user.created_at = ud.get("created_at", time.time())
                user.last_login = ud.get("last_login", 0)
                self._users[uid] = user
                self._api_key_index[user.api_key] = uid
        except Exception as e:
            logger.warning(f"[AUTH] Load failed: {e}")

    def get_status(self) -> Dict[str, Any]:
        return {
            "total_users": len(self._users),
            "active_users": sum(1 for u in self._users.values() if u.is_active),
            "roles": dict(
                (r.value, sum(1 for u in self._users.values() if u.role == r))
                for r in UserRole
            ),
        }
