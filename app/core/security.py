import secrets
import string
import hashlib
import jwt
from datetime import datetime, timedelta
from typing import Optional
from app.core.config import settings


def generate_api_key(prefix: str = "docai") -> str:
    """
    Generate a secure random API key with a prefix
    Format: prefix_random_32_chars
    Example: docai_AbC123xYz...
    """
    # Generate 32 character random string
    alphabet = string.ascii_letters + string.digits
    random_part = ''.join(secrets.choice(alphabet) for _ in range(32))

    return f"{prefix}_{random_part}"


def generate_hashed_api_key(api_key: str) -> str:
    """
    Hash the API key for secure storage in database
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """
    Verify if the provided API key matches the stored hash
    """
    provided_hash = hashlib.sha256(provided_key.encode()).hexdigest()
    return secrets.compare_digest(provided_hash, stored_hash)


def create_jwt_token(tenant_id: str, tenant_name: str, password: str, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT token for tenant authentication
    """
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(days=30)

    payload = {
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "password": password,
        "exp": expire
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_jwt_token(token: str) -> Optional[dict]:
    """
    Verify JWT token and return payload if valid
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def generate_api_key_from_details(name: str, email: str) -> str:
    """
    Generate API key based on name and email (less secure but deterministic)
    """
    # Create a base string from name and email
    base_string = f"{name}:{email}:{secrets.token_urlsafe(16)}"

    # Hash it and take first 32 characters
    api_key = hashlib.sha256(base_string.encode()).hexdigest()[:32]

    return f"docai_{api_key}"