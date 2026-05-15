"""
Symmetric encryption for the local config file using AES-256-GCM.

The encryption key itself is derived from a machine-stable secret
(stored in keychain) so that the config file is only usable on the
same machine by the same user.
"""

import json
import os
import stat
from pathlib import Path

import keyring
import keyring.errors
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_SERVICE = "claude-budget-hud"
_ENC_KEY_ACCOUNT = "config-enc-key"
_KEY_LEN = 32  # 256-bit


def _get_or_create_enc_key() -> bytes:
    """Retrieve or generate the AES key stored in the OS keychain.

    Falls back to a machine-local file key if no keychain backend is
    available (uncommon in production; e.g. headless Linux without
    a secret service daemon). The fallback file is chmod 600.
    """
    try:
        raw = keyring.get_password(_SERVICE, _ENC_KEY_ACCOUNT)
        if raw:
            return bytes.fromhex(raw)

        key = os.urandom(_KEY_LEN)
        keyring.set_password(_SERVICE, _ENC_KEY_ACCOUNT, key.hex())
        return key

    except keyring.errors.KeyringError:
        # No keychain backend — use a local key file as fallback
        return _file_fallback_key()


def _file_fallback_key() -> bytes:
    """Machine-local key file used when no keychain backend is available."""
    import platformdirs
    key_path = Path(platformdirs.user_data_dir("claude-budget-hud", "ssajaia")) / ".enc_key"
    key_path.parent.mkdir(parents=True, exist_ok=True)

    if key_path.exists():
        raw = key_path.read_bytes()
        if len(raw) == _KEY_LEN:
            return raw

    key = os.urandom(_KEY_LEN)
    key_path.write_bytes(key)
    _restrict_permissions(key_path)
    return key


def _config_path() -> Path:
    """Return platform-appropriate config directory."""
    import platformdirs
    base = Path(platformdirs.user_data_dir("claude-budget-hud", "ssajaia"))
    base.mkdir(parents=True, exist_ok=True)
    return base / "config.enc"


def _restrict_permissions(path: Path) -> None:
    """Set 600 permissions on Unix so only the owner can read."""
    if os.name != "nt":
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)


def save_config(data: dict) -> None:
    key = _get_or_create_enc_key()
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    plaintext = json.dumps(data).encode()
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    path = _config_path()
    # Write nonce + ciphertext separated by a null byte boundary marker
    with open(path, "wb") as f:
        f.write(nonce + ciphertext)
    _restrict_permissions(path)


def load_config() -> dict:
    path = _config_path()
    if not path.exists():
        return {}

    key = _get_or_create_enc_key()
    aesgcm = AESGCM(key)

    with open(path, "rb") as f:
        blob = f.read()

    if len(blob) < 12:
        return {}

    nonce = blob[:12]
    ciphertext = blob[12:]

    try:
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext.decode())
    except Exception:
        # Corrupted config — return defaults rather than crashing
        return {}
