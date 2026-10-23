#!/usr/bin/env python3
"""Foxpost csomagfigyelő – a kiküldött csomagok állapota a hivatalos Foxpost WebAPI-ból.

A csomaglista titkosítva van a repóban (a nyilvános repóban így senki nem látja a
címzetteket és a csomagszámokat):

    PBKDF2-SHA256(PKG_PASSWORD, SALT, 600 000 kör) -> 48 bájt
        0..31   AES-256-GCM kulcs
        32..47  fájlazonosító  ->  data/p/<id>.json

Környezeti változók (GitHub Secrets):
    PKG_PASSWORD                       – a csomagoldal jelszava
    FOXPOST_USER, FOXPOST_PASS, FOXPOST_APIKEY – Foxpost üzleti fiók (Beállítások)
    PKG_CMD (opcionális)               – parancs a weboldalról / Gmail-importból:
        "enc:<iv>.<ct>"  titkosított JSON {"add":[{"code","note","src"}], "remove":[code], "note":{code:note}}
        vagy sima szöveg: soronként egy csomagszám, utána opcionálisan " | megjegyzés"

Kézi használat:
    python3 scripts/packages.py               # frissítés
    python3 scripts/packages.py show          # visszafejtett lista kiírása
"""
import base64, hashlib, json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

SALT = b"matthewsfigs.hu/packages/v1"
INBOX_SALT = b"matthewsfigs.hu/packages/inbox-v1"   # csak parancsok titkosítására (Gmail-import)
ROUNDS = 600_000
OUT = Path(__file__).resolve().parent.parent / "data" / "p"
API = os.environ.get("FOXPOST_API", "https://webapi.foxpost.hu/api")

FINAL = {"RECEIVE", "HDRECEIVE", "RETURNDELIVERED", "BACKTOSENDER", "DESTROYED"}


def now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def derive(password):
    raw = hashlib.pbkdf2_hmac("sha256", password.strip().encode(), SALT, ROUNDS, 48)
    return raw[:32], raw[32:].hex()


def inbox_key(password):
    return hashlib.pbkdf2_hmac("sha256", password.strip().encode(), INBOX_SALT, ROUNDS, 32)


def seal(key, obj):
    iv = os.urandom(12)
    ct = AESGCM(key).encrypt(iv, json.dumps(obj, ensure_ascii=False).encode(), None)
    return iv, ct


def load(key, fid):
    f = OUT / f"{fid}.json"
    if not f.exists():
        return {"packages": []}
    blob = json.loads(f.read_text())
    pt = AESGCM(key).decrypt(base64.b64decode(blob["iv"]), base64.b64decode(blob["ct"]), None)
    return json.loads(pt)


def save(key, fid, data):
    iv, ct = seal(key, data)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{fid}.json").write_text(json.dumps(
        {"v": 1, "iv": base64.b64encode(iv).decode(), "ct": base64.b64encode(ct).decode()}))


def norm(code):
    return re.sub(r"\s+", "", code or "").upper()


def parse_cmd(key, raw, ikey=None):
    raw = (raw or "").strip()
    if not raw:
        return {}
    if raw[:4] in ("enc:", "inb:"):
        iv_b64, ct_b64 = raw[4:].split(".", 1)
        k = key if raw.startswith("enc:") else ikey
        pt = AESGCM(k).decrypt(base64.b64decode(iv_b64), base64.b64decode(ct_b64), None)
        return json.loads(pt)
    if os.environ.get("GITHUB_ACTIONS"):
        sys.exit("Titkosítatlan parancs a nyilvános naplóban – elutasítva.")
    add = []
    for line in raw.replace(",", "\n").splitlines():
        code, _, note = line.partition("|")
        if norm(code):
            add.append({"code": norm(code), "note": note.strip(), "src": "gmail"})
    return {"add": add}


def apply_cmd(data, cmd):
    pk = {p["code"]: p for p in data["packages"]}
    changed = False
    for a in cmd.get("add", []):
        code = norm(a.get("code"))
        if not code:
            continue
        if code in pk:
            if a.get("note") and not pk[code].get("note"):
                pk[code]["note"] = a["note"]
                changed = True
            continue
        p = {"code": code, "note": a.get("note", ""), "src": a.get("src", "kézi"),
             "added": now().isoformat()}
        data["packages"].append(p)
        pk[code] = p
        changed = True
    for code, note in (cmd.get("note") or {}).items():
        if norm(code) in pk:
            pk[norm(code)]["note"] = note
            changed = True
    if isinstance(cmd.get("gh"), str):      # a csomagoldal GitHub kulcsa (titkosítva marad a listában)
        if cmd["gh"].strip():
            data["gh"] = cmd["gh"].strip()
        else:
            data.pop("gh", None)
        changed = True
    rm = {norm(c) for c in cmd.get("remove", [])}
    if rm:
        before = len(data["packages"])
        data["packages"] = [p for p in data["packages"] if p["code"] not in rm]
        changed |= len(data["packages"]) != before
    return changed


def track(code, auth, apikey):
    req = urllib.request.Request(f"{API}/tracking/{urllib.request.quote(code)}", headers={
        "Authorization": "Basic " + auth, "Api-key": apikey,
        "Content-Type": "application/json", "Accept": "application/json",
        "User-Agent": "matthewsfigs.hu csomagfigyelo"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read()[:500].decode("utf-8", "replace")
        return e.code, {"_error": body}
    except Exception as e:  # hálózati hiba
        return 0, {"_error": str(e)[:200]}


def refresh(data):
    user, pw, apikey = (os.environ.get(k, "").strip() for k in ("FOXPOST_USER", "FOXPOST_PASS", "FOXPOST_APIKEY"))
    if not (user and pw and apikey):
        print("Nincsenek Foxpost kulcsok – lekérdezés kihagyva.")
        return
    auth = base64.b64encode(f"{user}:{pw}".encode()).decode()
    t = now()
    fails = 0
    for p in data["packages"]:
        # lezárt csomag: egy napig még nézzük (pl. visszaküldés), utána nem
        if p.get("final") and p.get("finalAt") and \
                datetime.fromisoformat(p["finalAt"]) < t - timedelta(days=1):
            continue
        code, res = track(p["code"], auth, apikey)
        p["checked"] = t.isoformat()
        if code == 200 and isinstance(res, dict) and res.get("traces") is not None:
            traces = res.get("traces") or []
            p.pop("error", None)
            p["clFox"] = res.get("clFox") or p["code"]
            p["eta"] = res.get("estimatedDelivery")
            p["sendType"] = res.get("sendType")
            p["parcelType"] = res.get("parcelType")
            p["related"] = res.get("relatedParcel")
            p["history"] = [{"s": tr.get("status"), "n": tr.get("longName") or tr.get("shortName"),
                             "sn": tr.get("shortName"), "d": tr.get("statusDate"),
                             "st": tr.get("statusStatidionId") or tr.get("statusStationId")}
                            for tr in traces]
            cur = p["history"][0] if p["history"] else {}
            p["status"] = cur.get("s")
            if p["status"] in FINAL:
                if not p.get("final"):
                    p["final"], p["finalAt"] = True, t.isoformat()
            else:
                p.pop("final", None); p.pop("finalAt", None)
        else:
            fails += 1
            p["error"] = {404: "A Foxpost nem ismeri ezt a csomagszámot (még).",
                          401: "Hibás Foxpost felhasználónév / jelszó.",
                          403: "A Foxpost elutasította (API-kulcs?).",
                          0: "A Foxpost nem érhető el."}.get(code, f"Foxpost hiba ({code})")
            p["errorDetail"] = str(res.get("_error", ""))[:300] if isinstance(res, dict) else ""
        time.sleep(0.3)
    data["checked"] = t.isoformat()
    print(f"Lekérdezve: {len(data['packages'])} csomag, {fails} hiba.")


# ---------- csomag létrehozása + címke (a csomagoldal "Csomagcímke létrehozása" gombja) ----------
JOBS = OUT / "j"


def creds():
    user, pw, apikey = (os.environ.get(k, "").strip() for k in ("FOXPOST_USER", "FOXPOST_PASS", "FOXPOST_APIKEY"))
    if not (user and pw and apikey):
        return None
    return base64.b64encode(f"{user}:{pw}".encode()).decode(), apikey


def api(method, path, body=None, pdf=False):
    auth, apikey = creds()
    req = urllib.request.Request(f"{API}{path}", method=method,
                                 data=None if body is None else json.dumps(body).encode(),
                                 headers={"Authorization": "Basic " + auth, "Api-key": apikey,
                                          "Content-Type": "application/json",
                                          "Accept": "application/pdf" if pdf else "application/json",
                                          "User-Agent": "matthewsfigs.hu csomagfigyelo"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.status, raw if pdf else json.loads(raw or b"{}")
    except urllib.error.HTTPError as e:
        raw = e.read()[:2000]
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"_error": raw.decode("utf-8", "replace")}


def errtext(res):
    """Foxpost hibaüzenet(ek) emberi formában."""
    out = []
    def walk(x):
        if isinstance(x, dict):
            if x.get("message") or x.get("field"):
                out.append(" ".join(str(v) for v in (x.get("field"), x.get("message")) if v))
            for k in ("errors", "parcels", "fieldErrors"):
                walk(x.get(k))
            if x.get("error") and isinstance(x["error"], str):
                out.append(x["error"])
            if x.get("_error"):
                out.append(str(x["_error"])[:200])
        elif isinstance(x, list):
            for y in x:
                walk(y)
    walk(res)
    hu = {"recipientName": "név", "recipientPhone": "telefonszám", "recipientEmail": "e-mail",
          "destination": "automata", "size": "méret", "cod": "utánvét", "INVALID_FORMAT": "hibás formátum",
          "INVALID_APM_ID": "ismeretlen", "REQUIRED": "hiányzik", "TOO_LONG": "túl hosszú"}
    txt = "; ".join(dict.fromkeys(o for o in out if o))[:400] or "ismeretlen hiba"
    for k, v in hu.items():
        txt = txt.replace(k, v)
    return txt


def write_job(key, rid, obj):
    JOBS.mkdir(parents=True, exist_ok=True)
    iv, ct = seal(key, obj)
    (JOBS / f"{rid}.json").write_text(json.dumps(
        {"v": 1, "iv": base64.b64encode(iv).decode(), "ct": base64.b64encode(ct).decode()}))


def create_parcels(key, data, jobs):
    done = data.setdefault("jobs", {})
    for j in jobs or []:
        rid = re.sub(r"[^a-f0-9]", "", str(j.get("rid", "")))[:32]
        if not rid or rid in done:
            continue
        if not creds():
            write_job(key, rid, {"ok": False, "error": "Nincsenek Foxpost kulcsok a GitHubon."})
            continue
        body = {"recipientName": j.get("nev", "")[:150], "recipientPhone": j.get("tel", ""),
                "recipientEmail": j.get("email", ""), "destination": str(j.get("aut", "")),
                "size": (j.get("size") or "s").lower(), "refCode": rid[:30]}
        if j.get("cod"):
            body["cod"] = int(j["cod"])
        if j.get("comment"):
            body["comment"] = str(j["comment"])[:50]
        st, res = api("POST", "/parcel?isWeb=true", [body])
        parcel = (res.get("parcels") or [{}])[0] if isinstance(res, dict) else {}
        code = parcel.get("clFoxId") or parcel.get("barcode") or parcel.get("newBarcode")
        if st not in (200, 201) or not code or res.get("valid") is False:
            print(f"Csomag létrehozása sikertelen ({st}).")
            write_job(key, rid, {"ok": False, "error": f"A Foxpost nem fogadta el: {errtext(res)}"})
            done[rid] = {"ok": False, "at": now().isoformat()}
            continue
        code = norm(code)
        note = j.get("note") or j.get("nev", "")
        if not any(p["code"] == code for p in data["packages"]):
            data["packages"].append({"code": code, "note": note, "src": "címke", "added": now().isoformat(),
                                     "status": "CREATE"})
        pdf = None
        for _ in range(3):
            pst, praw = api("POST", f"/label/{j.get('page') or 'A6'}", [code], pdf=True)
            if pst == 200 and isinstance(praw, bytes) and praw[:4] == b"%PDF":
                pdf = base64.b64encode(praw).decode()
                break
            time.sleep(3)
        write_job(key, rid, {"ok": True, "code": code, "pdf": pdf,
                             "error": None if pdf else "A csomag létrejött, de a címkét nem sikerült lekérni – a Foxpost felületén letöltheted."})
        done[rid] = {"ok": True, "code": code, "at": now().isoformat()}
        print("Csomag létrehozva" + (" + címke." if pdf else ", címke nélkül."))
    # régi címkefájlok és naplóbejegyzések takarítása (2 nap)
    lim = now() - timedelta(days=2)
    for rid, v in list(done.items()):
        if datetime.fromisoformat(v["at"]) < lim:
            done.pop(rid)
            f = JOBS / f"{rid}.json"
            if f.exists():
                f.unlink()


def cancel_parcels(key, data, items):
    """Még fel nem adott csomag sztornózása a Foxpostnál (DELETE /parcel/{barcode})."""
    done = data.setdefault("jobs", {})
    for it in items or []:
        rid = re.sub(r"[^a-f0-9]", "", str(it.get("rid", "")))[:32]
        code = norm(it.get("code"))
        if not rid or not code or rid in done:
            continue
        if not creds():
            write_job(key, rid, {"ok": False, "error": "Nincsenek Foxpost kulcsok a GitHubon."})
            continue
        st, res = api("DELETE", f"/parcel/{urllib.request.quote(code)}")
        ok = st in (200, 202, 204)
        if ok:
            data["packages"] = [p for p in data["packages"] if p["code"] != code]
        write_job(key, rid, {"ok": ok, "code": code,
                             "error": None if ok else f"A Foxpost nem törölte ({st}): {errtext(res)}"})
        done[rid] = {"ok": ok, "at": now().isoformat()}
        print("Sztornó: " + ("sikeres." if ok else f"sikertelen ({st})."))


def main():
    pw = os.environ.get("PKG_PASSWORD", "").strip()
    if not pw:
        print("Nincs PKG_PASSWORD – kihagyva.")
        return
    key, fid = derive(pw)
    data = load(key, fid)
    if len(sys.argv) > 1 and sys.argv[1] == "inboxkey":
        print(inbox_key(pw).hex())
        return
    if len(sys.argv) > 1 and sys.argv[1] == "show":
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    old = json.dumps(data.get("packages"), sort_keys=True, ensure_ascii=False)
    old_checked = data.get("checked")
    cmd = parse_cmd(key, os.environ.get("PKG_CMD"), inbox_key(pw))
    apply_cmd(data, cmd)
    create_parcels(key, data, cmd.get("create"))
    cancel_parcels(key, data, cmd.get("cancel"))
    refresh(data)
    # a "checked" mezőkön kívül változott-e valami?
    strip = lambda ps: json.dumps([{k: v for k, v in p.items() if k != "checked"} for p in ps or []],
                                  sort_keys=True, ensure_ascii=False)
    changed = strip(json.loads(old)) != strip(data["packages"])
    stale = not old_checked or datetime.fromisoformat(old_checked) < now() - timedelta(hours=3)
    if changed or stale or cmd or os.environ.get("PKG_FORCE") == "true":
        save(key, fid, data)
        print("Mentve." if changed else "Mentve (időbélyeg).")
    else:
        print("Nincs változás.")


if __name__ == "__main__":
    main()
