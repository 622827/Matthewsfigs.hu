#!/usr/bin/env python3
"""Pull the store inventory from the BrickLink API and write data/inventory.json.

Needs four secrets (env vars) from https://www.bricklink.com/v2/api/register_consumer.page :
  BL_CONSUMER_KEY, BL_CONSUMER_SECRET, BL_TOKEN, BL_TOKEN_SECRET
Optional: BL_STORE (default MatthewHorseman), STORE_CURRENCY (default HUF).
Only the Python standard library is used.
"""
import base64, hashlib, hmac, html, json, os, secrets, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.bricklink.com/api/store/v1"
STORE = os.environ.get("BL_STORE", "MatthewHorseman")
CURRENCY = os.environ.get("STORE_CURRENCY", "EUR")
OUT = Path(__file__).resolve().parent.parent / "data" / "inventory.json"

TYPE_LETTER = {"SET": "S", "MINIFIG": "M", "PART": "P", "BOOK": "B", "GEAR": "G",
               "CATALOG": "C", "INSTRUCTION": "I", "ORIGINAL_BOX": "O"}


def q(s):
    return urllib.parse.quote(str(s), safe="~")


def oauth_get(url, params=None):
    params = params or {}
    ck, cs = os.environ["BL_CONSUMER_KEY"], os.environ["BL_CONSUMER_SECRET"]
    tk, ts = os.environ["BL_TOKEN"], os.environ["BL_TOKEN_SECRET"]
    oauth = {
        "oauth_consumer_key": ck, "oauth_token": tk,
        "oauth_signature_method": "HMAC-SHA1", "oauth_timestamp": str(int(time.time())),
        "oauth_nonce": secrets.token_hex(16), "oauth_version": "1.0",
    }
    allp = {**params, **oauth}
    base_params = "&".join(f"{q(k)}={q(v)}" for k, v in sorted(allp.items()))
    base = "&".join(["GET", q(url), q(base_params)])
    key = f"{q(cs)}&{q(ts)}".encode()
    oauth["oauth_signature"] = base64.b64encode(hmac.new(key, base.encode(), hashlib.sha1).digest()).decode()
    header = "OAuth " + ", ".join(f'{k}="{q(v)}"' for k, v in oauth.items())
    full = url + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(full, headers={"Authorization": header})
    with urllib.request.urlopen(req, timeout=60) as r:
        body = json.load(r)
    meta = body.get("meta", {})
    if meta.get("code") != 200:
        sys.exit(f"BrickLink API error: {meta}")
    return body["data"]


def image_url(item_type, no, color_id):
    letter = TYPE_LETTER.get(item_type, "S")
    color = color_id if item_type == "PART" else 0
    return f"https://img.bricklink.com/ItemImage/{letter}N/{color}/{urllib.parse.quote(no)}.png"


SECRETS = ("BL_CONSUMER_KEY", "BL_CONSUMER_SECRET", "BL_TOKEN", "BL_TOKEN_SECRET")


def main():
    missing = [k for k in SECRETS if not os.environ.get(k)]
    if missing:
        # No API keys yet: keep the current inventory.json and finish quietly.
        print("::notice::BrickLink API-kulcsok még nincsenek beállítva "
              f"({', '.join(missing)}); a készlet nem frissült.")
        return
    rows = oauth_get(f"{API}/inventories")
    items = []
    parts_lots = parts_qty = 0
    for r in rows:
        if r.get("is_stock_room"):
            continue  # not publicly for sale
        it = r["item"]
        if it["type"] == "PART":
            parts_lots += 1
            parts_qty += r.get("quantity", 0)
            continue  # parts are browsed on BrickLink, not listed on the site
        if it["type"] not in ("SET", "MINIFIG"):
            continue
        try:
            price = round(float(r.get("unit_price") or 0), 2) or None
        except ValueError:
            price = None
        items.append({
            "id": r["inventory_id"],
            "type": it["type"],
            "no": it["no"],
            "name": html.unescape(urllib.parse.unquote(it.get("name", ""))),
            "color": r.get("color_name") if it["type"] == "PART" and r.get("color_id") else None,
            "cond": r.get("new_or_used", "N"),
            "qty": r.get("quantity", 0),
            "price": price,
            "note": (r.get("description") or "").strip(),
            "img": image_url(it["type"], it["no"], r.get("color_id", 0)),
            "url": f"https://www.bricklink.com/store.asp?p={STORE}&itemID={r['inventory_id']}",
        })
    order = {"SET": 0, "MINIFIG": 1, "PART": 2}
    items.sort(key=lambda i: (order.get(i["type"], 3), -(i["price"] or 0)))
    payload = {
        "store": STORE, "currency": CURRENCY, "total_lots": len(items) + parts_lots,
        "parts_lots": parts_lots, "parts_qty": parts_qty, "items": items,
    }
    # Only touch the file when the stock really changed, so frequent runs
    # don't create a commit (and a site rebuild) every time.
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
            old.pop("updated", None)
            if old == payload:
                print("Nincs változás a készletben.")
                return
        except ValueError:
            pass
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), **payload,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {len(items)} sets/minifigs (+{parts_lots} part lots) to {OUT}")


if __name__ == "__main__":
    main()
