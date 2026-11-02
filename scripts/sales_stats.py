#!/usr/bin/env python3
"""BrickLink sales totals: how many sets, minifigures, parts … we have sold so far.

Reads every incoming BrickLink order (open and filed), leaves out cancelled / unpaid ones,
adds up the order items by type and year, and saves the result ENCRYPTED with the package
page key (PKG_PASSWORD) to data/p/s/<id>.json – nothing is printed to the public Actions log.
"""
import base64, json, os, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_bricklink as BL          # noqa: E402
from packages import derive, seal    # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "data" / "p" / "s"
SKIP = {"CANCELLED", "PURGED", "NPB", "NPX", "NRS", "NSS"}   # cancelled or never paid


def main():
    pw = os.environ.get("PKG_PASSWORD", "").strip()
    if not pw:
        sys.exit("Nincs PKG_PASSWORD.")
    orders = {}
    for filed in ("false", "true"):
        for o in BL.oauth_get(f"{BL.API}/orders", {"direction": "in", "filed": filed}) or []:
            orders[o["order_id"]] = o
    print(f"{len(orders)} rendelés.")
    by_type = defaultdict(lambda: {"qty": 0, "lots": 0, "eur": 0.0})
    by_year = defaultdict(lambda: defaultdict(int))
    status, skipped, counted = defaultdict(int), 0, 0
    total = defaultdict(float)
    first = last = None
    for oid, o in sorted(orders.items()):
        st = (o.get("status") or "").upper()
        status[st] += 1
        if st in SKIP:
            skipped += 1
            continue
        counted += 1
        year = (o.get("date_ordered") or "")[:4]
        d = (o.get("date_ordered") or "")[:10]
        first = min(first or d, d); last = max(last or d, d)
        cost = o.get("cost") or {}
        total[cost.get("currency_code") or "?"] += float(cost.get("subtotal") or 0)
        batches = BL.oauth_get(f"{BL.API}/orders/{oid}/items") or []
        for batch in batches:
            for it in batch:
                t = (it.get("item") or {}).get("type") or "?"
                q = int(it.get("quantity") or 0)
                by_type[t]["qty"] += q
                by_type[t]["lots"] += 1
                by_type[t]["eur"] += q * float(it.get("unit_price_final") or it.get("unit_price") or 0)
                by_year[year][t] += q
    res = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "orders": counted, "skipped": skipped,
           "status": dict(status), "first": first, "last": last, "subtotal": {k: round(v, 2) for k, v in total.items()},
           "by_type": {k: {**v, "eur": round(v["eur"], 2)} for k, v in by_type.items()},
           "by_year": {y: dict(v) for y, v in sorted(by_year.items())}}
    key, fid = derive(pw)
    iv, ct = seal(key, res)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{fid}.json").write_text(json.dumps({"v": 1, "iv": base64.b64encode(iv).decode(), "ct": base64.b64encode(ct).decode()}))
    # public: only the total number of items sold (homepage counter)
    sold = sum(v["qty"] for v in by_type.values())
    (OUT.parent.parent / "sales.json").write_text(json.dumps({"sold": sold, "updated": res["at"]}) + "\n")
    print("Mentve (titkosítva) + data/sales.json.")


if __name__ == "__main__":
    main()
