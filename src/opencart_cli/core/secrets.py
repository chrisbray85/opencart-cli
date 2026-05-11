"""Secret storage with OS keychain + env var fallback.

Strategy:
  1. If keyring is available and working, prefer it (macOS Keychain /
     Linux Secret Service / Windows Credential Manager).
  2. Else fall back to env vars (great for CI / headless servers).
  3. Plaintext in config file is supported but discouraged — users get
     a warning on first use.
"""

from __future__ import annotations

import os

try:
    import keyring
    import keyring.errors

    _KEYRING_OK = True
except ImportError:  # pragma: no cover
    _KEYRING_OK = False


SERVICE_NAME = "opencart-cli"


def _keyring_username(profile: str, key: str) -> str:
    """Compose a stable keyring identifier from profile + key."""
    return f"{profile}::{key}"


def get_secret(profile: str, key: str, env_var: str | None = None) -> str | None:
    """Resolve a secret in this order: env var → keyring → None.

    Args:
        profile: profile name (e.g. "rewnd")
        key:     secret kind (e.g. "db_password")
        env_var: optional env var name to check first (e.g. "OPENCART_DB_PASS")
    """
    if env_var:
        val = os.environ.get(env_var)
        if val:
            return val

    if _KEYRING_OK:
        try:
            return keyring.get_password(SERVICE_NAME, _keyring_username(profile, key))
        except keyring.errors.KeyringError:
            return None
    return None


def set_secret(profile: str, key: str, value: str) -> bool:
    """Store a secret in the OS keychain. Returns True on success.

    Returns False if keyring is unavailable — caller can fall back to
    storing in config (with a warning) or prompting per-command.
    """
    if not _KEYRING_OK:
        return False
    try:
        keyring.set_password(SERVICE_NAME, _keyring_username(profile, key), value)
        return True
    except keyring.errors.KeyringError:
        return False


def delete_secret(profile: str, key: str) -> bool:
    """Remove a secret from the keychain. Returns True if a value existed."""
    if not _KEYRING_OK:
        return False
    try:
        keyring.delete_password(SERVICE_NAME, _keyring_username(profile, key))
        return True
    except (keyring.errors.PasswordDeleteError, keyring.errors.KeyringError):
        return False


def keyring_available() -> bool:
    """Whether the OS keychain is reachable on this machine."""
    if not _KEYRING_OK:
        return False
    try:
        # Probe with a no-op get — exceptions reveal misconfigured backends.
        keyring.get_password(SERVICE_NAME, "__probe__")
        return True
    except keyring.errors.KeyringError:
        return False
