#!/usr/bin/env python3
"""Szett–minifigura „háló” a termékoldalakhoz → data/graph.json

Minden szett és figura, ami a mi termékeinkből kiindulva szett ↔ figura lépésekkel elérhető,
saját termékoldalt kap (ahonnan be tudjuk szerezni).

  - A kapcsolatok (melyik szettben mely figurák vannak) a Rebrickable nyilvános, szabadon
    letölthető adatbázisából jönnek – korlát nélkül.
  - A figurák a BrickLink-számukkal (pl. sw0298) jelennek meg: szettenként egyetlen BrickLink
    API-hívással (subsets) lekérjük a szett figuráit, és név szerint párosítjuk a Rebrickable-
    figurákkal. A párosítást (data/graph_map.json) megőrizzük, így minden szettet csak egyszer
    kérdezünk le; futásonként legfeljebb MAP_MAX-ot.
  - Párosítatlan figura a Rebrickable-azonosítójával (fig-000123) szerepel.

graph.json:  {"sets": {"7913-1": [név, év, elemszám, [[figura, db], ...]]}, "figs": {"sw0298": név, ...}}
"""
import csv, gzip, io, json, os, re, sys, urllib.parse, urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sync_bricklink import API, SECRETS, oauth_get  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
INV = ROOT / "data" / "inventory.json"
DETAILS = ROOT / "data" / "details.json"
OUT = ROOT / "data" / "graph.json"
MAP = ROOT / "data" / "graph_map.json"
RB = "https://cdn.rebrickable.com/media/downloads/"
MAP_MAX = int(os.environ.get("GRAPH_MAP_MAX", "100"))
MAX_NODES = 6000


def rows(name):
    req = urllib.request.Request(RB + name + ".csv.gz", headers={"User-Agent": "matthewsfigs.hu"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return list(csv.DictReader(io.TextIOWrapper(gzip.GzipFile(fileobj=io.BytesIO(r.read())), encoding="utf-8")))


def words(s):
    s = re.sub(r"[^a-z0-9]+", " ", str(s).lower())
    return {w for w in s.split() if len(w) > 1 and w not in {"the", "and", "with", "of", "minifig", "minifigure"}}


def bl_figs(no):
    """BrickLink: minifigures of a set [[bl_no, qty, name]], or None on API error / quota."""
    try:
        subs = oauth_get(f"{API}/items/SET/{urllib.parse.quote(no)}/subsets")
    except (Exception, SystemExit) as e:
        print(f"  ! {no}: {e}")
        return None
    figs = {}
    for g in subs:
        for e in g.get("entries", []):
            if e.get("is_alternate") or e.get("is_counterpart"):
                continue
            i = e.get("item", {})
            if i.get("type") == "MINIFIG":
                f = figs.setdefault(i["no"], [i["no"], 0, urllib.parse.unquote(i.get("name", ""))])
                f[1] += int(e.get("quantity") or 0)
    return sorted(figs.values())


def match(rb_list, bl_list):
    """Pair Rebrickable and BrickLink figures of the same set by name (greedy, best word overlap first)."""
    cand = []
    for rf, rq, rn in rb_list:
        rw = words(rn)
        for bf, bq, bn in bl_list:
            bw = words(bn)
            j = len(rw & bw) / max(1, len(rw | bw))
            cand.append((j + (0.15 if rq == bq else 0), rf, bf))
    cand.sort(reverse=True)
    used_r, used_b, out = set(), set(), {}
    for score, rf, bf in cand:
        if score < 0.2 or rf in used_r or bf in used_b:
            continue
        used_r.add(rf); used_b.add(bf); out[rf] = bf
    # a single figure on both sides always pairs up
    left_r = [r for r in rb_list if r[0] not in used_r]; left_b = [b for b in bl_list if b[0] not in used_b]
    if len(left_r) == 1 and len(left_b) == 1:
        out[left_r[0][0]] = left_b[0][0]
    return out


def main():
    inv = json.loads(INV.read_text(encoding="utf-8"))
    det = json.loads(DETAILS.read_text(encoding="utf-8")).get("items", {}) if DETAILS.exists() else {}
    mp = json.loads(MAP.read_text(encoding="utf-8")) if MAP.exists() else {"bl": {}}
    have_keys = all(os.environ.get(k) for k in SECRETS)
    # cheap exit: graph already built today and nothing left to map
    if OUT.exists() and mp.get("built") == date.today().isoformat() and (not have_keys or not mp.get("todo")):
        print("A háló ma már elkészült, nincs párosítandó szett.")
        return

    sets = {r["set_num"]: r for r in rows("sets")}
    figs = {r["fig_num"]: r for r in rows("minifigs")}
    invs = {r["id"]: r["set_num"] for r in rows("inventories") if r["version"] == "1"}
    s2f, f2s = {}, {}
    for r in rows("inventory_minifigs"):
        s = invs.get(r["inventory_id"])
        if s:
            s2f.setdefault(s, {})[r["fig_num"]] = s2f.get(s, {}).get(r["fig_num"], 0) + int(r["quantity"] or 0)
            f2s.setdefault(r["fig_num"], set()).add(s)

    # seeds: our sets + the sets our minifigures come in
    seeds = {i["no"] for i in inv.get("items", []) if i.get("type") == "SET"}
    for d in det.values():
        for s in d.get("sets") or []:
            seeds.add(s["no"])
        for v in d.get("versions") or []:
            seeds.add(v["no"])
    comp, seen_f, q = set(), set(), [s for s in seeds if s in s2f]
    while q and len(comp) + len(seen_f) < MAX_NODES:
        s = q.pop()
        if s in comp:
            continue
        comp.add(s)
        for f in s2f.get(s, {}):
            if f not in seen_f:
                seen_f.add(f)
                q += [x for x in f2s.get(f, ()) if x not in comp]
    comp |= {s for s in seeds if s in sets}
    print(f"Háló: {len(comp)} szett, {len(seen_f)} figura.")

    # BrickLink figure lists: from details.json (already fetched) or one subsets call per set
    bl = mp.get("bl", {})
    for n, d in det.items():
        if d.get("type") == "SET" and d.get("minifigs") is not None and n not in bl:
            bl[n] = [[f["no"], f["qty"], f["name"]] for f in d["minifigs"]]
    # sets around our own stock first (so e.g. a Battle Pack with our clone trooper gets its BrickLink numbers early)
    todo = sorted((n for n in comp if n not in bl and s2f.get(n)), key=lambda n: (n not in seeds, n))
    done = 0
    if have_keys:
        for n in todo[:MAP_MAX]:
            r = bl_figs(n)
            if r is None:
                break
            bl[n] = r
            done += 1
    print(f"BrickLink-párosítás: {done} új szett, {max(0, len(todo) - done)} van még hátra.")

    # Rebrickable fig -> BrickLink fig (majority vote over all sets where both lists are known)
    votes = {}
    for n, blist in bl.items():
        rlist = [[f, qn, figs.get(f, {}).get("name", f)] for f, qn in (s2f.get(n) or {}).items()]
        for rf, bf in match(rlist, blist).items():
            votes.setdefault(rf, {}).setdefault(bf, 0)
            votes[rf][bf] += 1
    # partial lists before the subsets call: the BrickLink minifigures we already know to be in a set
    # (from their own "appears in" list), e.g. our sw0299 → 7913-1
    known = {}
    for fno, d in det.items():
        if d.get("type") == "MINIFIG":
            for s in d.get("sets") or []:
                known.setdefault(s["no"], []).append([fno, 0, d.get("name") or fno])
    for n, blist in known.items():
        if n in bl:
            continue
        rlist = [[f, qn, figs.get(f, {}).get("name", f)] for f, qn in (s2f.get(n) or {}).items()]
        for rf, bf in match(rlist, blist).items():
            votes.setdefault(rf, {}).setdefault(bf, 0)
            votes[rf][bf] += 1
    rb2bl = {rf: max(v, key=v.get) for rf, v in votes.items()}

    out_sets, out_figs = {}, {}
    for n in sorted(comp):
        s = sets.get(n)
        if not s:
            continue
        if n in bl:   # exact BrickLink list
            fl = [[f, qn] for f, qn, nm in bl[n]]
            for f, qn, nm in bl[n]:
                out_figs.setdefault(f, nm)
        else:
            fl = []
            for f, qn in sorted((s2f.get(n) or {}).items()):
                fid = rb2bl.get(f, f)
                fl.append([fid, qn])
                out_figs.setdefault(fid, figs.get(f, {}).get("name", fid))
        out_sets[n] = [s["name"], int(s["year"] or 0) or None, int(s["num_parts"] or 0) or None, fl]
    OUT.write_text(json.dumps({"_info": "Szett–minifigura háló (scripts/catalog_graph.py): Rebrickable kapcsolatok, BrickLink-figuraszámok.",
                               "sets": out_sets, "figs": dict(sorted(out_figs.items())),
                               "alias": dict(sorted(rb2bl.items()))},   # old Rebrickable links -> BrickLink number
                              ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    MAP.write_text(json.dumps({"built": date.today().isoformat(), "todo": max(0, len(todo) - done), "bl": dict(sorted(bl.items()))},
                              ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Mentve: {len(out_sets)} szett, {len(out_figs)} figura ({len(rb2bl)} párosítva).")


if __name__ == "__main__":
    main()
