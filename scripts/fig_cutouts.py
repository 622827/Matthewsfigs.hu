#!/usr/bin/env python3
"""Cut the minifigures out of their white BrickLink background (transparent PNG),
for the "display stand" turntable on the site.

Output: assets/figs/<no>.png and assets/figs/index.json {"sw0314": {"r": 0.62}}  (r = width / height)
Only new figures are processed unless --force.
Requires: pip install opencv-python-headless numpy
"""
import json, sys, urllib.request
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "figs"
INV = ROOT / "data" / "inventory.json"
H_PX = 360  # output height


def fetch(no):
    url = f"https://img.bricklink.com/ItemImage/MN/0/{no}.png"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 matthewsfigs.hu"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = np.frombuffer(r.read(), np.uint8)
    except Exception:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def cutout(bgr):
    h, w = bgr.shape[:2]
    # background = near-white pixels connected to the border (white armour inside the outline stays)
    near_white = (bgr.min(axis=2) >= 246).astype(np.uint8)
    pad = np.pad(near_white, 1, constant_values=1)
    mask = np.zeros((h + 4, w + 4), np.uint8)
    flood = pad.copy() * 255
    cv2.floodFill(flood, mask, (0, 0), 128, loDiff=0, upDiff=0, flags=4)
    bg = (flood[1:-1, 1:-1] == 128)
    fg = (~bg).astype(np.uint8) * 255
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    # keep the main blobs only (drop specks)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg, 8)
    if n <= 1:
        return None
    keep = np.zeros_like(fg)
    big = stats[1:, cv2.CC_STAT_AREA].max()
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= 0.01 * big:
            keep[lab == i] = 255
    # soft 1px edge
    alpha = cv2.GaussianBlur(keep, (3, 3), 0)
    ys, xs = np.where(keep > 0)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgba = np.dstack([bgr, alpha])[y0:y1, x0:x1]
    s = H_PX / rgba.shape[0]
    rgba = cv2.resize(rgba, (max(1, int(round(rgba.shape[1] * s))), H_PX), interpolation=cv2.INTER_CUBIC)
    return rgba


def main():
    force = "--force" in sys.argv
    OUT.mkdir(parents=True, exist_ok=True)
    idx_path = OUT / "index.json"
    index = json.loads(idx_path.read_text()) if idx_path.exists() else {}
    figs = sorted({i["no"] for i in json.loads(INV.read_text())["items"] if i["type"] == "MINIFIG"})
    ok = failed = 0
    for no in figs:
        if no in index and not force:
            continue
        img = fetch(no)
        res = cutout(img) if img is not None else None
        if res is None:
            index[no] = None
            failed += 1
            continue
        cv2.imwrite(str(OUT / f"{no}.png"), res, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        index[no] = {"r": round(res.shape[1] / res.shape[0], 4)}
        ok += 1
    idx_path.write_text(json.dumps(index, indent=1, sort_keys=True))
    print(f"Kész: {ok} figura, {failed} sikertelen.")


if __name__ == "__main__":
    main()
