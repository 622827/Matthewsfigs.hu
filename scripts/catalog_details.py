#!/usr/bin/env python3
"""BrickLink katalógusadatok a termékoldalakhoz → data/details.json

A hivatalos BrickLink API-ból (ugyanazokkal a kulcsokkal, mint a készletszinkron)
tényadatokat tölt le minden szetthez és minifigurához:
  szett: megjelenés éve, téma (kategória), elemszám, minifigurák listája, doboz mérete, súly
  figura: megjelenés éve, téma, mely szettekben szerepel
Csak a hiányzó vagy 90 napnál régebbi tételeket kéri le, futásonként legfeljebb MAX_ITEMS-et,
így bőven belefér a BrickLink napi API-keretébe. Hiba esetén a meglévő adatok maradnak.
"""
import csv, gzip, html, io, json, os, re, sys, urllib.parse, urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_bricklink import API, SECRETS, oauth_get  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INV = ROOT / "data" / "inventory.json"
OUT = ROOT / "data" / "details.json"
MAX_ITEMS = int(os.environ.get("DETAILS_MAX", "80"))
STALE_DAYS = 90


def get(path, params=None):
    try:
        return oauth_get(API + path, params)   # query params must go here: they are part of the OAuth signature
    except (Exception, SystemExit) as e:   # oauth_get exits on API errors
        print(f"  ! {path}: {e}")
        return None


def clean(s):
    return html.unescape(urllib.parse.unquote(str(s or ""))).strip()


def num(v):
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


REBRICKABLE_SETS = "https://cdn.rebrickable.com/media/downloads/sets.csv.gz"   # nyilvános, szabadon letölthető adatbázis
_RB = None


def rb_sets():
    """Rebrickable set list: normalized name -> [{no, name, year, pieces, img}] (only real sets, 20+ pieces)."""
    global _RB
    if _RB is None:
        _RB = {}
        try:
            req = urllib.request.Request(REBRICKABLE_SETS, headers={"User-Agent": "matthewsfigs.hu"})
            with urllib.request.urlopen(req, timeout=60) as r:
                rows = csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(r.read())), encoding="utf-8"))
                for row in rows:
                    try:
                        pcs = int(row["num_parts"] or 0)
                    except ValueError:
                        pcs = 0
                    if pcs < 20:
                        continue
                    _RB.setdefault(norm_name(row["name"]), []).append({
                        "no": row["set_num"], "name": row["name"], "year": int(row["year"] or 0) or None,
                        "pieces": pcs, "img": row["img_url"]})
        except Exception as e:
            print(f"  ! Rebrickable-lista: {e}")
    return _RB


def norm_name(s):
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower().replace("’", "'")).strip()


def versions_of(no, name):
    """Other releases with the same name (e.g. 6210 / 75020 / 75397 Jabba's Sail Barge)."""
    same = rb_sets().get(norm_name(name), [])
    if len(same) < 2 or not any(v["no"] == no for v in same):
        return []
    return sorted(same, key=lambda v: (v["year"] or 0, v["no"]))


# Brickset API (ingyenes kulcs: brickset.com/tools/webservices/requestkey → GitHub Secret BRICKSET_API_KEY):
# hivatalos kiegészítő fotók, eredeti bolti ár (DE, EUR), megjelenés és kivezetés dátuma
BS_KEY = os.environ.get("BRICKSET_API_KEY", "")
BS_API = "https://brickset.com/api/v3.asmx/"
BS_MAX = int(os.environ.get("BRICKSET_MAX", "40"))    # getSets napi kerete szűk: futásonként legfeljebb ennyi szett


def bs(method, **params):
    q = urllib.parse.urlencode({"apiKey": BS_KEY, **params})
    try:
        req = urllib.request.Request(BS_API + method + "?" + q, headers={"User-Agent": "matthewsfigs.hu"})
        with urllib.request.urlopen(req, timeout=40) as r:
            j = json.load(r)
        if j.get("status") != "success":
            print(f"  ! Brickset {method}: {j.get('message')}")
            return None
        return j
    except Exception as e:
        print(f"  ! Brickset {method}: {e}")
        return None


def brickset(no):
    """Photos + retail price + dates for one set, or None if Brickset is unavailable."""
    j = bs("getSets", userHash="", params=json.dumps({"setNumber": no}))
    if not j or not j.get("sets"):
        return None if j is None else {"bs_id": None}
    s = j["sets"][0]
    photos = [s.get("image", {}).get("imageURL")]
    if s.get("additionalImageCount"):
        a = bs("getAdditionalImages", setID=s["setID"])
        photos += [im.get("imageURL") for im in (a or {}).get("additionalImages", [])]
    de = (s.get("LEGOCom") or {}).get("DE") or {}
    return {"bs_id": s.get("setID"), "photos": [p for p in photos if p][:24],
            "retail_eur": de.get("retailPrice"), "launch": (de.get("dateFirstAvailable") or "")[:10] or None,
            "exit": (de.get("dateLastAvailable") or s.get("exitDate") or "")[:10] or None}


CATS = {}
FIGSETS = {}   # minifig no -> number of sets it appears in (persisted in details.json "figsets")


def fig_set_count(no):
    if no in FIGSETS:
        return FIGSETS[no]
    sup = get(f"/items/MINIFIG/{urllib.parse.quote(no)}/supersets")
    if sup is None:
        return None
    n = len({e["item"]["no"] for g in sup for e in g.get("entries", []) if e.get("item", {}).get("type") == "SET"})
    FIGSETS[no] = n
    return n


def category(cid):
    if not cid:
        return None
    if cid not in CATS:
        c = get(f"/categories/{cid}") or {}
        CATS[cid] = clean(c.get("category_name")) or None
    return CATS[cid]


def fetch(item_type, no):
    seg = urllib.parse.quote(no)
    it = get(f"/items/{item_type}/{seg}")
    if not it:
        return None
    d = {
        "type": item_type,
        "name": clean(it.get("name")),
        "year": it.get("year_released") or None,
        "category": category(it.get("category_id")),
        "weight_g": num(it.get("weight")),
        "dims_cm": [x for x in (num(it.get("dim_x")), num(it.get("dim_y")), num(it.get("dim_z"))) if x] or None,
        "fetched": date.today().isoformat(),
    }
    if item_type == "SET":
        subs = get(f"/items/SET/{seg}/subsets")
        if subs is not None:
            pieces, figs = 0, {}
            for group in subs:
                for e in group.get("entries", []):
                    if e.get("is_alternate") or e.get("is_counterpart"):
                        continue
                    i = e.get("item", {})
                    if i.get("type") == "PART":
                        pieces += int(e.get("quantity") or 0)
                    elif i.get("type") == "MINIFIG":
                        f = figs.setdefault(i["no"], {"no": i["no"], "name": clean(i.get("name")), "qty": 0})
                        f["qty"] += int(e.get("quantity") or 0)
            d["pieces"] = pieces or None
            for f in figs.values():
                f["sets"] = fig_set_count(f["no"])   # 1 = exclusive to this set
            d["minifigs"] = sorted(figs.values(), key=lambda f: f["no"])
        d["versions"] = [{"no": v["no"], "name": v["name"], "year": v["year"], "pieces": v["pieces"], "img": v["img"]}
                         for v in versions_of(no, d["name"])]
    elif item_type == "MINIFIG":
        sup = get(f"/items/MINIFIG/{seg}/supersets")
        if sup is not None:
            sets = {}
            for group in sup:
                for e in group.get("entries", []):
                    i = e.get("item", {})
                    if i.get("type") == "SET":
                        sets[i["no"]] = {"no": i["no"], "name": clean(i.get("name"))}
            d["sets"] = sorted(sets.values(), key=lambda s: s["no"])[:30]
            FIGSETS[no] = len(sets)
    return d


def main():
    if any(not os.environ.get(k) for k in SECRETS):
        print("::notice::BrickLink API-kulcsok nincsenek beállítva; a katalógusadatok nem frissültek.")
        return
    inv = json.loads(INV.read_text(encoding="utf-8"))
    out = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    items = out.get("items", {})
    FIGSETS.update(out.get("figsets", {}))
    wanted = {}
    for i in inv.get("items", []):
        if i.get("type") in ("SET", "MINIFIG"):
            wanted[i["no"]] = i["type"]
    today = date.today()

    def stale(no):
        d = items.get(no)
        if not d or (d.get("type") == "SET" and "versions" not in d):
            return True
        try:
            return (today - date.fromisoformat(d.get("fetched", "2000-01-01"))).days > STALE_DAYS
        except ValueError:
            return True

    todo = [no for no in sorted(wanted, key=lambda n: (n in items, n)) if stale(no)][:MAX_ITEMS]
    print(f"{len(todo)} tétel lekérése ({sum(1 for n in wanted if n not in items)} hiányzik).")
    changed = False
    for no in todo:
        d = fetch(wanted[no], no)
        if d:
            items[no] = d
            changed = True
            print(f"  {no}: {d.get('year')} · {d.get('category')} · {d.get('pieces', '')}")
    # Brickset: fotók, bolti ár, dátumok (csak ha van kulcs; egyszer szettenként)
    if BS_KEY:
        bs_todo = [n for n, d in items.items() if d.get("type") == "SET" and "bs_id" not in d and n in wanted][:BS_MAX]
        print(f"Brickset: {len(bs_todo)} szett.")
        for n in bs_todo:
            r = brickset(n)
            if r is None:
                break          # API-hiba vagy elfogyott a napi keret: a következő futás folytatja
            items[n].update(r)
            changed = True

    if not changed:
        print("Nincs új katalógusadat.")
        return
    OUT.write_text(json.dumps({
        "_info": "BrickLink katalógusadatok (scripts/catalog_details.py). Tényadatok, a termékoldal adattáblázatához.",
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "items": dict(sorted(items.items())),
        "figsets": dict(sorted(FIGSETS.items())),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Mentve: {OUT}")


if __name__ == "__main__":
    main()
