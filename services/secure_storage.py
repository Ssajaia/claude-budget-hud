"""
Secure API key storage using the OS-native keychain.

- Windows  → Credential Manager
- macOS    → Keychain
- Linux    → libsecret / GNOME Keyring (requires python3-secretstorage)

The key is NEVER written to disk, logged, or exposed after storage.
"""

import keyring
import keyring.errors

SERVICE_NAME = "claude-budget-hud"
API_KEY_ACCOUNT = "anthropic-api-key"


class SecureStorage:
    def store_api_key(self, api_key: str) -> None:
        """Store API key in OS keychain. Raises on failure."""
        if not api_key or not api_key.strip():
            raise ValueError("API key must not be empty.")
        keyring.set_password(SERVICE_NAME, API_KEY_ACCOUNT, api_key.strip())

    def get_api_key(self) -> str | None:
        """Retrieve API key. Returns None if not set."""
        try:
            return keyring.get_password(SERVICE_NAME, API_KEY_ACCOUNT)
        except keyring.errors.KeyringError:
            return None

    def delete_api_key(self) -> None:
        """Remove API key from keychain."""
        try:
            keyring.delete_password(SERVICE_NAME, API_KEY_ACCOUNT)
        except keyring.errors.PasswordDeleteError:
            pass  # Already gone — not an error

    def has_api_key(self) -> bool:
        key = self.get_api_key()
        return bool(key and key.strip())
