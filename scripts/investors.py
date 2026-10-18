#!/usr/bin/env python3
"""Encrypt / decrypt the password-protected investor pages.

Every investor has their own password. The password alone decides which file
is opened and decrypts it, so nothing secret is ever stored in the repository:

    PBKDF2-SHA256(password, SALT, 600 000 rounds) -> 48 bytes
        bytes  0..31  AES-256-GCM key
        bytes 32..47  file id  ->  data/i/<id>.json

Usage
    python3 scripts/investors.py encrypt <source.json> "<password>"
    python3 scripts/investors.py decrypt "<password>"   > source.json

Keep the plaintext source files OUT of the repository (see .gitignore).
Requires: pip install cryptography
"""
import base64, hashlib, json, os, sys
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SALT = b"matthewsfigs.hu/investors/v1"
ROUNDS = 600_000
OUT = Path(__file__).resolve().parent.parent / "data" / "i"


def derive(password):
    raw = hashlib.pbkdf2_hmac("sha256", password.strip().encode("utf-8"), SALT, ROUNDS, 48)
    return raw[:32], raw[32:].hex()


def encrypt(src, password):
    data = json.loads(Path(src).read_text(encoding="utf-8"))
    key, fid = derive(password)
    iv = os.urandom(12)
    ct = AESGCM(key).encrypt(iv, json.dumps(data, ensure_ascii=False).encode("utf-8"), None)
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / f"{fid}.json"
    out.write_text(json.dumps({"v": 1, "iv": base64.b64encode(iv).decode(),
                               "ct": base64.b64encode(ct).decode()}), encoding="utf-8")
    print(f"OK: {data.get('investor', '?')} -> {out.relative_to(OUT.parent.parent)}")


def decrypt(password):
    key, fid = derive(password)
    f = OUT / f"{fid}.json"
    if not f.exists():
        sys.exit("Ehhez a jelszóhoz nincs befektetői oldal.")
    blob = json.loads(f.read_text(encoding="utf-8"))
    pt = AESGCM(key).decrypt(base64.b64decode(blob["iv"]), base64.b64decode(blob["ct"]), None)
    print(json.dumps(json.loads(pt), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "encrypt":
        encrypt(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == "decrypt":
        decrypt(sys.argv[2])
    else:
        sys.exit(__doc__)
