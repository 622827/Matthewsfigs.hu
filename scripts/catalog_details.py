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
UCS_THEMES = {171}       # Rebrickable: Ultimate Collector Series
AUTO = ROOT / "data" / "autolabels.json"
_RBTHEME = {}
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
                    try:
                        _RBTHEME[row["set_num"]] = int(row["theme_id"] or 0)
                    except ValueError:
                        pass
                    if pcs < 20:
                        continue
                    _RB.setdefault(norm_name(row["name"]), []).append({
                        "no": row["set_num"], "name": row["name"], "year": int(row["year"] or 0) or None,
                        "pieces": pcs, "img": row["img_url"]})
        except Exception as e:
            print(f"  ! Rebrickable-lista: {e}")
    return _RB


_RBFIGS = None


def rb_fig_counts():
    """Rebrickable: number of minifigures per set (main inventory version)."""
    global _RBFIGS
    if _RBFIGS is None:
        _RBFIGS = {}
        try:
            def rows(name):
                req = urllib.request.Request(f"https://cdn.rebrickable.com/media/downloads/{name}.csv.gz", headers={"User-Agent": "matthewsfigs.hu"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    return list(csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(r.read())), encoding="utf-8")))
            inv = {r["id"]: r["set_num"] for r in rows("inventories") if r["version"] == "1"}
            for r in rows("inventory_minifigs"):
                s = inv.get(r["inventory_id"])
                if s:
                    _RBFIGS[s] = _RBFIGS.get(s, 0) + int(r["quantity"] or 0)
        except Exception as e:
            print(f"  ! Rebrickable minifigura-lista: {e}")
    return _RBFIGS


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


def bs_desc(s):
    """LEGO's official product text (Brickset extendedData.description) as plain paragraphs."""
    raw = ((s.get("extendedData") or {}).get("description") or "").strip()
    if not raw:
        return ""
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</li>|</h\d>", "\n", raw)
    raw = re.sub(r"(?i)<li[^>]*>", "• ", raw)
    txt = html.unescape(re.sub(r"<[^>]+>", "", raw))
    paras = [re.sub(r"[ \t]+", " ", x).strip() for x in txt.split("\n")]
    return "\n".join(x for x in paras if x)


def brickset_desc(no):
    """Only the official description (for sets fetched before descriptions were stored). None on API error."""
    j = bs("getSets", userHash="", params=json.dumps({"setNumber": no, "extendedData": 1}))
    if j is None:
        return None
    return bs_desc(j["sets"][0]) if j.get("sets") else ""


def brickset(no):
    """Photos + retail price + dates + official description for one set, or None if Brickset is unavailable."""
    j = bs("getSets", userHash="", params=json.dumps({"setNumber": no, "extendedData": 1}))
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
            "exit": (de.get("dateLastAvailable") or s.get("exitDate") or "")[:10] or None,
            "desc_en": bs_desc(s)}


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
        rb_sets()
        d["ucs"] = _RBTHEME.get(no) in UCS_THEMES
        vs = versions_of(no, d["name"])
        figs_n = rb_fig_counts() if vs else {}
        d["versions"] = [{"no": v["no"], "name": v["name"], "year": v["year"], "pieces": v["pieces"], "img": v["img"],
                          "figs": figs_n.get(v["no"], 0)} for v in vs]
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


FIGVAL_MAX = int(os.environ.get("FIGVAL_MAX", "60"))   # price-guide calls per run
FIGVAL_DAYS = 30
PRICES = ROOT / "data" / "prices_huf.json"


def fig_value(no):
    """Average BrickLink sale price of a minifigure in the last 6 months, EUR (new; used as fallback)."""
    for cond in ("N", "U"):
        r = get(f"/items/MINIFIG/{urllib.parse.quote(no)}/price",
                {"guide_type": "sold", "new_or_used": cond, "currency_code": "EUR"})
        if r is None:
            return None, None
        v = num(r.get("qty_avg_price")) or num(r.get("avg_price"))
        if v:
            return round(v, 2), cond
    return 0.0, None


def update_fig_values(items, wanted, figval, today):
    """Refresh the market value of the minifigures of the sets we sell (oldest first, FIGVAL_MAX per run)
    and store, per set, what its minifigures are worth in HUF (for the 'set only, no minifigures' price)."""
    need = sorted({f["no"] for n, d in items.items() if n in wanted and d.get("type") == "SET" for f in d.get("minifigs") or []})
    def old(no):
        try:
            return (today - date.fromisoformat(figval.get(no, {}).get("at", "2000-01-01"))).days > FIGVAL_DAYS
        except ValueError:
            return True
    todo = [n for n in sorted(need, key=lambda n: figval.get(n, {}).get("at", "")) if old(n)][:FIGVAL_MAX]
    changed = False
    for no in todo:
        v, cond = fig_value(no)
        if v is None:
            break                        # API problem: try again next run
        figval[no] = {"eur": v, "cond": cond, "at": today.isoformat()}
        changed = True
    rate = 366.33
    try:
        rate = json.loads(PRICES.read_text(encoding="utf-8")).get("rate", rate)
    except Exception:
        pass
    for n, d in items.items():
        if d.get("type") != "SET" or not d.get("minifigs"):
            continue
        figs = d["minifigs"]
        if all(f["no"] in figval for f in figs):
            huf = round(sum(f["qty"] * figval[f["no"]]["eur"] for f in figs) * rate)
            if d.get("figs_value_huf") != huf:
                d["figs_value_huf"] = huf
                changed = True
    if todo:
        print(f"Figuraértékek: {len(todo)} frissítve.")
    return changed


def write_autolabels(items, wanted, today):
    """Automatic labels for the shop: UCS (Rebrickable theme) and Retired (Brickset exit date passed)."""
    auto = {}
    for n, t in sorted(wanted.items()):
        d = items.get(n) or {}
        if t != "SET":
            continue
        out = []
        if d.get("ucs"):
            out.append("UCS")
        if d.get("exit") and d["exit"] < today.isoformat():
            out.append("Retired")
        if out:
            auto[n] = out
    text = json.dumps({"_info": "Automatikus címkék (scripts/catalog_details.py): UCS a Rebrickable témája, Retired a Brickset kivezetési dátuma alapján.",
                       "labels": auto}, ensure_ascii=False, indent=1) + "\n"
    if not AUTO.exists() or AUTO.read_text(encoding="utf-8") != text:
        AUTO.write_text(text, encoding="utf-8")
        print(f"Automatikus címkék: {len(auto)} szett.")


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
        if not d or (d.get("type") == "SET" and ("versions" not in d or "ucs" not in d
                                                 or any("figs" not in v for v in d["versions"]))):
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
            keep = {k: v for k, v in (items.get(no) or {}).items() if k in ("bs_id", "photos", "retail_eur", "launch", "exit", "figs_value_huf", "desc_en", "gallery")}
            items[no] = {**keep, **d}     # Brickset data is fetched once; keep it on refresh
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
        # official LEGO description for sets that were fetched before we stored it (same daily quota)
        left = BS_MAX - len(bs_todo)
        desc_todo = [n for n, d in items.items() if d.get("type") == "SET" and d.get("bs_id") and "desc_en" not in d and n in wanted][:max(0, left)]
        if desc_todo:
            print(f"Brickset leírás: {len(desc_todo)} szett.")
        for n in desc_todo:
            r = brickset_desc(n)
            if r is None:
                break
            items[n]["desc_en"] = r
            changed = True

    figval = out.get("figvalues", {})
    changed = update_fig_values(items, wanted, figval, today) or changed
    write_autolabels(items, wanted, today)
    if not changed:
        print("Nincs új katalógusadat.")
        return
    OUT.write_text(json.dumps({
        "_info": "BrickLink katalógusadatok (scripts/catalog_details.py). Tényadatok, a termékoldal adattáblázatához.",
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "items": dict(sorted(items.items())),
        "figsets": dict(sorted(FIGSETS.items())),
        "figvalues": dict(sorted(figval.items())),
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Mentve: {OUT}")


if __name__ == "__main__":
    main()
