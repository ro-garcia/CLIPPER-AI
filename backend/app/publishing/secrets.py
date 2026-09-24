"""Per-user Windows DPAPI token storage. Database rows contain references only."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
from uuid import uuid4

from ..config import settings


class DATA_BLOB(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]


def _blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_char))), buffer


class SecureTokenStore:
    def __init__(self, root: Path | None = None):
        self.root = root or settings.storage_dir / 'secrets'
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _crypt(data: bytes, protect: bool) -> bytes:
        if os.name != 'nt':
            raise RuntimeError('El almacenamiento real de tokens requiere Windows DPAPI.')
        source, keepalive = _blob(data)
        target = DATA_BLOB()
        if protect:
            success = ctypes.windll.crypt32.CryptProtectData(
                ctypes.byref(source), 'LiveClip AI', None, None, None, 0, ctypes.byref(target))
        else:
            success = ctypes.windll.crypt32.CryptUnprotectData(
                ctypes.byref(source), None, None, None, None, 0, ctypes.byref(target))
        if not success:
            raise ctypes.WinError()
        try:
            return ctypes.string_at(target.pbData, target.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(target.pbData)

    def save(self, value: dict, reference: str = '') -> str:
        reference = reference or uuid4().hex
        path = self.root / f'{reference}.bin'
        temporary = self.root / f'.{reference}.tmp'
        temporary.write_bytes(self._crypt(json.dumps(value, separators=(',', ':')).encode(), True))
        temporary.replace(path)
        return reference

    def load(self, reference: str) -> dict:
        if not reference or any(char not in '0123456789abcdef' for char in reference.lower()):
            raise ValueError('Referencia de credencial inválida.')
        return json.loads(self._crypt((self.root / f'{reference}.bin').read_bytes(), False))

    def delete(self, reference: str):
        if reference and all(char in '0123456789abcdef' for char in reference.lower()):
            (self.root / f'{reference}.bin').unlink(missing_ok=True)
