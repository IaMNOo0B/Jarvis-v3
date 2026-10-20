"""Secret storage backed exclusively by Windows Credential Manager.

No file, environment-variable, or plaintext fallback is provided. On non-Windows
systems operations fail explicitly so callers cannot mistake a fallback for secure storage.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from typing import Protocol


class CredentialStoreError(RuntimeError):
    """Credential storage could not complete safely."""


class CredentialBackend(Protocol):
    def write(self, target: str, secret: str) -> None: ...
    def read(self, target: str) -> str | None: ...
    def delete(self, target: str) -> None: ...


class WindowsCredentialBackend:
    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2
    ERROR_NOT_FOUND = 1168

    class CREDENTIALW(ctypes.Structure):
        _fields_ = [
            ("Flags", wintypes.DWORD),
            ("Type", wintypes.DWORD),
            ("TargetName", wintypes.LPWSTR),
            ("Comment", wintypes.LPWSTR),
            ("LastWritten", wintypes.FILETIME),
            ("CredentialBlobSize", wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_byte)),
            ("Persist", wintypes.DWORD),
            ("AttributeCount", wintypes.DWORD),
            ("Attributes", ctypes.c_void_p),
            ("TargetAlias", wintypes.LPWSTR),
            ("UserName", wintypes.LPWSTR),
        ]

    def __init__(self) -> None:
        if os.name != "nt":
            raise CredentialStoreError("Windows Credential Manager is available only on Windows.")
        self._advapi = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
        self._advapi.CredWriteW.argtypes = [ctypes.POINTER(self.CREDENTIALW), wintypes.DWORD]
        self._advapi.CredWriteW.restype = wintypes.BOOL
        self._advapi.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(ctypes.POINTER(self.CREDENTIALW))]
        self._advapi.CredReadW.restype = wintypes.BOOL
        self._advapi.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
        self._advapi.CredDeleteW.restype = wintypes.BOOL
        self._advapi.CredFree.argtypes = [ctypes.c_void_p]
        self._advapi.CredFree.restype = None

    def write(self, target: str, secret: str) -> None:
        if not secret:
            raise ValueError("Secret must not be empty.")
        blob = secret.encode("utf-16-le")
        blob_buffer = (ctypes.c_byte * len(blob)).from_buffer_copy(blob)
        credential = self.CREDENTIALW()
        credential.Type = self.CRED_TYPE_GENERIC
        credential.TargetName = target
        credential.CredentialBlobSize = len(blob)
        credential.CredentialBlob = ctypes.cast(blob_buffer, ctypes.POINTER(ctypes.c_byte))
        credential.Persist = self.CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = "JARVIS"
        if not self._advapi.CredWriteW(ctypes.byref(credential), 0):
            raise CredentialStoreError("Windows Credential Manager could not save the secret.")

    def read(self, target: str) -> str | None:
        credential_ptr = ctypes.POINTER(self.CREDENTIALW)()
        if not self._advapi.CredReadW(target, self.CRED_TYPE_GENERIC, 0, ctypes.byref(credential_ptr)):
            code = ctypes.get_last_error()
            if code == self.ERROR_NOT_FOUND:
                return None
            raise CredentialStoreError("Windows Credential Manager could not read the secret.")
        try:
            credential = credential_ptr.contents
            raw = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
            try:
                return raw.decode("utf-16-le")
            except UnicodeDecodeError as exc:
                raise CredentialStoreError("Stored credential has an invalid encoding.") from exc
        finally:
            self._advapi.CredFree(credential_ptr)

    def delete(self, target: str) -> None:
        if not self._advapi.CredDeleteW(target, self.CRED_TYPE_GENERIC, 0):
            code = ctypes.get_last_error()
            if code != self.ERROR_NOT_FOUND:
                raise CredentialStoreError("Windows Credential Manager could not delete the secret.")


class CredentialStore:
    """Namespaced secret API with an injectable backend for isolated tests."""

    _PREFIX = "JARVIS.v3/"

    def __init__(self, backend: CredentialBackend | None = None) -> None:
        self._backend = backend if backend is not None else WindowsCredentialBackend()

    @classmethod
    def _target(cls, name: str) -> str:
        normalized = name.strip().casefold()
        if not normalized or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789._-" for ch in normalized):
            raise ValueError("Credential name may contain only letters, digits, dot, underscore, and hyphen.")
        return cls._PREFIX + normalized

    def set_secret(self, name: str, secret: str) -> None:
        if not isinstance(secret, str) or not secret:
            raise ValueError("Secret must not be empty.")
        self._backend.write(self._target(name), secret)

    def get_secret(self, name: str) -> str | None:
        return self._backend.read(self._target(name))

    def delete_secret(self, name: str) -> None:
        self._backend.delete(self._target(name))
