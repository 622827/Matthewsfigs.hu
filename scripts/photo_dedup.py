#!/usr/bin/env python3
"""Duplikált termékfotók kiszűrése a termékoldal galériájához.

A galéria: BrickLink doboz (ON), BrickLink megépített szett (SN), majd a Brickset-fotók.
Ugyanaz a kép gyakran több forrásból is megvan (pl. a Brickset főképe = a BrickLink dobozképe),
ezért minden képből „ujjlenyomatot” (dHash) számolunk a fehér keret levágása után, és ami egy
korábbi képpel szinte egyezik, kimarad. Eredmény: details.json → items[no]["gallery"].

  python3 scripts/photo_dedup.py            # a még nem ellenőrzött szettek
  python3 scripts/photo_dedup.py --all      # minden szett újra
Requires: pip install pillow
"""
import io, json, sys, urllib.parse, urllib.request
from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
DETAILS = ROOT / "data" / "details.json"
BL = "https://img.bricklink.com/ItemImage/"
LIMIT = 10          # Hamming distance (of 64 bits) under which two pictures count as the same


def load(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 matthewsfigs.hu"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return Image.open(io.BytesIO(r.read())).convert("RGB")
    except Exception:
        return None


def dhash(img):
    """64-bit difference hash of the picture with its white margin trimmed off."""
    bg = Image.new("RGB", img.size, (255, 255, 255))
    box = ImageChops.difference(img, bg).convert("L").point(lambda v: 255 if v > 18 else 0).getbbox()
    if box:
        img = img.crop(box)
    g = img.convert("L").resize((9, 8), Image.LANCZOS)
    px = list(g.getdata())
    bits = 0
    for y in range(8):
        for x in range(8):
            bits = (bits << 1) | (px[y * 9 + x] > px[y * 9 + x + 1])
    return bits, img.width / max(1, img.height)


def gallery(no, photos):
    enc = urllib.parse.quote(no)
    cands = [f"{BL}ON/0/{enc}.png", f"{BL}SN/0/{enc}.png"] + list(photos or [])
    kept, seen = [], []
    for url in cands:
        img = load(url)
        if img is None:
            continue
        h, ar = dhash(img)
        if any(bin(h ^ h2).count("1") <= LIMIT and abs(ar - ar2) < 0.25 * max(ar, ar2) for h2, ar2 in seen):
            continue
        seen.append((h, ar))
        kept.append(url)
    return kept


def run(items, everything=False):
    changed = False
    for no, d in items.items():
        if d.get("type") != "SET" or (not everything and "gallery" in d):
            continue
        g = gallery(no, d.get("photos"))
        if g and g != d.get("gallery"):
            d["gallery"] = g
            changed = True
            print(f"  {no}: {len(g)} kép ({2 + len(d.get('photos') or []) - len(g)} duplikált/hiányzó kimaradt)")
    return changed


if __name__ == "__main__":
    data = json.loads(DETAILS.read_text(encoding="utf-8"))
    if run(data.get("items", {}), "--all" in sys.argv):
        DETAILS.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print("Mentve.")
