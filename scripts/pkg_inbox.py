#!/usr/bin/env python3
"""Csomagszámok titkosított beküldése a csomagfigyelőnek (pl. a Gmail-importból).

    python3 scripts/pkg_inbox.py <INBOX_KEY_HEX> "CLFOX123… | megjegyzés" ["CLFOX456… | …" …]

Kiírja a titkosított parancsot ("inb:…"), amit a packages.yml workflow `cmd` bemenete fogad.
Az inbox-kulcs csak parancsokat tud titkosítani – a csomaglistát nem nyitja.
"""
import base64, json, os, re, sys
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

key = bytes.fromhex(sys.argv[1])
add = []
for arg in sys.argv[2:]:
    code, _, note = arg.partition("|")
    code = re.sub(r"\s+", "", code).upper()
    if code:
        add.append({"code": code, "note": note.strip(), "src": "gmail"})
if not add:
    sys.exit("Nincs csomagszám.")
iv = os.urandom(12)
ct = AESGCM(key).encrypt(iv, json.dumps({"add": add}, ensure_ascii=False).encode(), None)
print(f"inb:{base64.b64encode(iv).decode()}.{base64.b64encode(ct).decode()}")
