#!/usr/bin/env python3
"""Change the price of one BrickLink store lot: python scripts/bl_price.py <lot id> <EUR price>.

Used by the "BrickLink-ár" workflow. Only the lot id and the new price are involved,
so nothing personal reaches the public Actions log.
"""
import base64, hashlib, hmac, json, os, secrets, sys, time, urllib.error, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_bricklink import API, q, oauth_get   # noqa: E402


def oauth_put(url, payload):
    ck, cs = os.environ["BL_CONSUMER_KEY"], os.environ["BL_CONSUMER_SECRET"]
    tk, ts = os.environ["BL_TOKEN"], os.environ["BL_TOKEN_SECRET"]
    oauth = {"oauth_consumer_key": ck, "oauth_token": tk, "oauth_signature_method": "HMAC-SHA1",
             "oauth_timestamp": str(int(time.time())), "oauth_nonce": secrets.token_hex(16), "oauth_version": "1.0"}
    base_params = "&".join(f"{q(k)}={q(v)}" for k, v in sorted(oauth.items()))
    base = "&".join(["PUT", q(url), q(base_params)])
    oauth["oauth_signature"] = base64.b64encode(hmac.new(f"{q(cs)}&{q(ts)}".encode(), base.encode(), hashlib.sha1).digest()).decode()
    header = "OAuth " + ", ".join(f'{k}="{q(v)}"' for k, v in oauth.items())
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="PUT",
                                 headers={"Authorization": header, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read()
    try:
        body = json.loads(raw)
    except ValueError:
        sys.exit(f"Nem JSON válasz ({len(raw)} bájt): {raw[:200]!r}")
    if body.get("meta", {}).get("code") != 200:
        sys.exit(f"BrickLink API error: {body.get('meta')}")
    return body["data"]


def main():
    lot, price = sys.argv[1], f"{float(sys.argv[2]):.4f}"
    if not lot.isdigit():
        sys.exit("Hibás tételazonosító.")
    out = Path(__file__).resolve().parent.parent / "data" / "bl_price_last.json"
    res = {"lot": lot, "eur": price, "at": time.strftime("%Y-%m-%d %H:%M:%S")}
    try:
        try:
            res["before"] = oauth_get(f"{API}/inventories/{lot}").get("unit_price")
        except Exception as e:
            res["get_error"] = repr(e)[:200]
        after = oauth_put(f"{API}/inventories/{lot}", {"unit_price": price})
        res.update(ok=True, after=after.get("unit_price"), no=after.get("item", {}).get("no"))
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
