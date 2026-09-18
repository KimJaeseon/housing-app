"""Persistent Windows current-user DPAPI credential; never print secret values."""
import argparse
import ctypes
from ctypes import wintypes
import getpass
import os
from pathlib import Path
import tempfile
import warnings

KEY_FILE = Path(__file__).resolve().parents[1] / '.secrets' / 'lh-service-key.dpapi'
MAGIC = b'HOUSING-LH-DPAPI-1\n'


class KeyStoreError(Exception):
    """Only constant, credential-free error messages are exposed."""


def _crypt(data, decrypt=False):
    if os.name != 'nt':
        raise KeyStoreError('Windows DPAPI is required for the local key file')

    class Blob(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]

    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source = Blob(len(data), buffer)
    target = Blob()
    crypt32 = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    function = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    try:
        # UI_FORBIDDEN only: deliberately do not enable LOCAL_MACHINE scope.
        if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
            raise KeyStoreError('Local key encryption or decryption failed')
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        ctypes.memset(buffer, 0, len(data))
        if target.pbData:
            ctypes.memset(target.pbData, 0, target.cbData)
            kernel32.LocalFree(target.pbData)


def save_key(key, path=None):
    from backend.lh_probe import normalize_key
    path = Path(path) if path is not None else KEY_FILE
    temporary = None
    try:
        normalized = normalize_key(key)
        if len(normalized) > 4096:
            raise ValueError('invalid_key')
        encrypted = MAGIC + _crypt(normalized.encode('utf-8'))
        path.parent.mkdir(parents=True, exist_ok=True)
        # Even the temporary file contains ciphertext only. Replace atomically.
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.key-', delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(encrypted)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except (OSError, ValueError):
        raise KeyStoreError('Could not save a valid local key') from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def load_key(path=None):
    from backend.lh_probe import normalize_key
    path = Path(path) if path is not None else KEY_FILE
    try:
        with path.open('rb') as handle:
            encrypted = handle.read(16385)
    except FileNotFoundError:
        return ''
    except OSError:
        raise KeyStoreError('Could not read the local key file') from None
    try:
        if len(encrypted) > 16384 or not encrypted.startswith(MAGIC):
            raise ValueError('invalid_file')
        return normalize_key(_crypt(encrypted[len(MAGIC):], decrypt=True).decode('utf-8'))
    except (OSError, ValueError):
        raise KeyStoreError('Local key file is invalid or unavailable for this Windows account') from None


def resolve_key():
    """Explicit server environment overrides the local encrypted file."""
    return os.environ.get('LH_SERVICE_KEY', '').strip() or load_key()


def main(argv=None):
    parser = argparse.ArgumentParser(description='Save or check an encrypted LH key; no key argument accepted.')
    parser.add_argument('action', choices=['save', 'status'])
    args = parser.parse_args(argv)
    try:
        if args.action == 'status':
            present = bool(load_key())
            print('Local encrypted key: ready' if present else 'Local encrypted key: not configured')
            return 0 if present else 2
        with warnings.catch_warnings():
            warnings.simplefilter('error', getpass.GetPassWarning)
            key = getpass.getpass('LH service key (hidden; Enter to save): ')
        save_key(key)
        print('Encrypted key saved. Future runs will load it automatically.')
        return 0
    except (KeyStoreError, EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print('Key operation failed. Use a Windows terminal and a valid service key; no key was displayed.')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
