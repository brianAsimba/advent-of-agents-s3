"""A local Cloud KMS stand-in with real AES-256-GCM envelope encryption.

Each object gets its own data key, and that data key is stored only in wrapped form. Without the key version, the
stored bytes can't be read, so disabling a version is a kill switch and destroying one erases the data for good.
"""
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ENABLED, DISABLED, DESTROYED = "ENABLED", "DISABLED", "DESTROYED"


class KeyUnavailable(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code, self.detail = code, detail


class KMS:
    def __init__(self):
        self.keys: dict[str, dict] = {}

    def create_key(self, name: str, region: str) -> None:
        self.keys[name] = {"region": region, "primary": 1, "versions": {1: {"material": AESGCM.generate_key(256), "state": ENABLED}}}

    def rotate(self, name: str) -> int:
        """New data uses the new version; old versions keep decrypting what they already wrapped."""
        key = self.keys[name]
        key["primary"] = max(key["versions"]) + 1
        key["versions"][key["primary"]] = {"material": AESGCM.generate_key(256), "state": ENABLED}
        return key["primary"]

    def set_state(self, name: str, version: int, state: str) -> None:
        v = self.keys[name]["versions"][version]
        if v["state"] == DESTROYED:
            raise KeyUnavailable("KEY_DESTROYED", f"{name} version {version} is destroyed and cannot change state")
        v["state"] = state
        if state == DESTROYED:
            v["material"] = None

    def _usable(self, name: str, version: int) -> bytes:
        v = self.keys[name]["versions"][version]
        if v["state"] == DISABLED:
            raise KeyUnavailable("KEY_DISABLED", f"{name} version {version} is disabled")
        if v["state"] == DESTROYED:
            raise KeyUnavailable("KEY_DESTROYED", f"{name} version {version} is destroyed; this data is unrecoverable")
        return v["material"]

    def encrypt(self, name: str, plaintext: bytes, aad: bytes) -> dict:
        version = self.keys[name]["primary"]
        kek = self._usable(name, version)
        dek = AESGCM.generate_key(256)
        data_nonce, wrap_nonce = os.urandom(12), os.urandom(12)
        return {"key": name, "version": version, "data_nonce": data_nonce, "wrap_nonce": wrap_nonce,
                "wrapped_dek": AESGCM(kek).encrypt(wrap_nonce, dek, aad),
                "ciphertext": AESGCM(dek).encrypt(data_nonce, plaintext, aad)}

    def decrypt(self, blob: dict, aad: bytes) -> bytes:
        kek = self._usable(blob["key"], blob["version"])
        try:
            dek = AESGCM(kek).decrypt(blob["wrap_nonce"], blob["wrapped_dek"], aad)
            return AESGCM(dek).decrypt(blob["data_nonce"], blob["ciphertext"], aad)
        except InvalidTag as e:
            raise KeyUnavailable("INTEGRITY_FAILED", "the stored object was altered or moved") from e
