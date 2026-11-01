#!/usr/bin/env python3
"""Fix forintárak az oldalon.

A BrickLink EUR-árból egyszer, rögzített árfolyamon kiszámolt forintár
bekerül a data/prices_huf.json-ba, és onnantól nem változik, akkor sem, ha a
BrickLinken módosul az ár. A szinkron csak az új tételeknek számol árat.

Kézi parancsok (a végén mindig frissül a data/inventory.json is):
  python3 scripts/huf_prices.py reset 75020-1 sw0314   # újraszámolás a mostani BL-árból
  python3 scripts/huf_prices.py reset --all            # minden tétel újraszámolása
  python3 scripts/huf_prices.py set 75020-1 149990     # kézi forintár
  python3 scripts/huf_prices.py rate 370               # új árfolyam (csak új / reset tételekre)
  python3 scripts/huf_prices.py apply                  # csak alkalmazás
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRICES = ROOT / "data" / "prices_huf.json"
INV = ROOT / "data" / "inventory.json"
DEFAULT = {
    "_info": "Fix forintárak BrickLink-tételazonosító (lot id) szerint. A szinkron nem írja felül; "
             "módosítás: scripts/huf_prices.py. Kerekítés: legközelebbi 500 Ft − 20, így minden ár 480-ra vagy 980-ra végződik.",
    "rate": 366.33,
    "rate_note": "ECB EUR/HUF, 2026-10-30",
    "items": {},
}


def load():
    if PRICES.exists():
        return json.loads(PRICES.read_text(encoding="utf-8"))
    return json.loads(json.dumps(DEFAULT))


def save(p):
    p["items"] = dict(sorted(p["items"].items(), key=lambda kv: (kv[1]["no"], kv[0])))
    PRICES.write_text(json.dumps(p, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def to_huf(eur, rate):
    if not eur:
        return None
    # legközelebbi 500 Ft, majd -20: mindig 480-ra vagy 980-ra végződik
    return max(500, int(round(eur * rate / 500)) * 500) - 20


def apply(items, p):
    """Set item["price"] to the fixed HUF price (adding new items to the table).
    item["eur"] keeps the BrickLink price. Returns True if the table changed."""
    changed = False
    table = p["items"]
    for i in items:
        if "eur" not in i:
            i["eur"] = i.get("price")
        key = str(i["id"])
        if key not in table and i["eur"]:
            table[key] = {"no": i["no"], "huf": to_huf(i["eur"], p["rate"])}
            changed = True
        i["price"] = table[key]["huf"] if key in table else None
    return changed


def apply_to_inventory(p):
    inv = json.loads(INV.read_text(encoding="utf-8"))
    apply(inv["items"], p)
    inv["currency"] = "HUF"
    INV.write_text(json.dumps(inv, ensure_ascii=False, indent=1), encoding="utf-8")


def main(argv):
    if not argv:
        sys.exit(__doc__)
    cmd, args = argv[0], argv[1:]
    p = load()
    inv = json.loads(INV.read_text(encoding="utf-8"))["items"]
    if cmd == "reset":
        want = set(args)
        hits = [i for i in inv if "--all" in want or i["no"] in want or i["no"].removesuffix("-1") in want]
        for i in hits:
            eur = i.get("eur", i.get("price"))
            p["items"].pop(str(i["id"]), None)
            if eur:
                p["items"][str(i["id"])] = {"no": i["no"], "huf": to_huf(eur, p["rate"])}
            print(f'{i["no"]}: {eur} EUR -> {p["items"].get(str(i["id"]), {}).get("huf")} Ft')
        missing = want - {"--all"} - {i["no"] for i in hits} - {i["no"].removesuffix("-1") for i in hits}
        if missing:
            sys.exit(f"Nincs ilyen tétel: {', '.join(sorted(missing))}")
    elif cmd == "set":
        no, huf = args[0], int(args[1])
        hits = [i for i in inv if i["no"] in (no, no + "-1")]
        if not hits:
            sys.exit(f"Nincs ilyen tétel: {no}")
        for i in hits:
            p["items"][str(i["id"])] = {"no": i["no"], "huf": huf}
            print(f'{i["no"]} ({i["id"]}): {huf} Ft')
    elif cmd == "rate":
        p["rate"] = float(args[0])
        p["rate_note"] = " ".join(args[1:]) or "kézi árfolyam"
    elif cmd != "apply":
        sys.exit(__doc__)
    apply_to_inventory(p)
    save(p)


if __name__ == "__main__":
    main(sys.argv[1:])
