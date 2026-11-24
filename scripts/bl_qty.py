#!/usr/bin/env python3
"""Set the quantity of one BrickLink store lot: python scripts/bl_qty.py <lot id> <new qty>.

Used by the "BrickLink-készlet módosítása" workflow. The BrickLink API takes the
change as a signed difference ("-1", "+2"), so the current quantity is read first.
"""
import json, sys, time, urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_bricklink import API, oauth_get   # noqa: E402
from bl_price import oauth_put              # noqa: E402


def main():
    lot, target = sys.argv[1], int(sys.argv[2])
    if not lot.isdigit() or target < 0:
        sys.exit("Hibás tételazonosító vagy mennyiség.")
    out = Path(__file__).resolve().parent.parent / "data" / "bl_qty_last.json"
    res = {"lot": lot, "target": target, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        cur = oauth_get(f"{API}/inventories/{lot}")
        before = int(cur.get("quantity", 0))
        res.update(no=cur.get("item", {}).get("no"), before=before)
        delta = target - before
        if delta == 0:
            res.update(ok=True, after=before, note="nem kellett változtatni")
        else:
            after = oauth_put(f"{API}/inventories/{lot}", {"quantity": f"{delta:+d}"})
            res.update(ok=True, after=after.get("quantity"))
    except SystemExit as e:
        res.update(ok=False, error=str(e))
    except urllib.error.HTTPError as e:
        res.update(ok=False, error=f"HTTP {e.code}: {e.read()[:300].decode('utf-8', 'replace')}")
    except Exception as e:
        res.update(ok=False, error=repr(e)[:300])
    out.write_text(json.dumps(res, ensure_ascii=False) + "\n")
    print(res)
    if not res["ok"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
