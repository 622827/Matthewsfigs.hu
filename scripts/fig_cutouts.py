#!/usr/bin/env python3
"""Cut the minifigures out of their white BrickLink background (transparent PNG),
for the "display stand" turntable on the site.

Output: assets/figs/<no>.webp and assets/figs/index.json {"sw0314": {"r": 0.62}}  (r = width / height)
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
H_PX = 280  # output height


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
    # background = pixels close to the photo's border colour, connected to the border
    border = np.concatenate([bgr[0], bgr[-1], bgr[:, 0], bgr[:, -1]])
    bgc = np.median(border, axis=0)
    dist = np.abs(bgr.astype(np.int16) - bgc.astype(np.int16)).max(axis=2)
    near_bg = (dist <= 16).astype(np.uint8)
    pad = np.pad(near_bg, 1, constant_values=1) * 255
    mask = np.zeros((h + 4, w + 4), np.uint8)
    cv2.floodFill(pad, mask, (0, 0), 128, loDiff=0, upDiff=0, flags=4)
    fg = (pad[1:-1, 1:-1] != 128).astype(np.uint8) * 255
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    # keep only the figure itself: the biggest blob (drops spare heads / accessories shown beside it)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg, 8)
    if n <= 1:
        return None
    main_i = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    keep = (lab == main_i).astype(np.uint8) * 255
    keep = cv2.morphologyEx(keep, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    # background pockets enclosed by the figure (gap between arm and body, between the legs)
    tight = ((dist <= 7) & (keep > 0)).astype(np.uint8)
    m, plab, pst, _ = cv2.connectedComponentsWithStats(tight, 4)
    for i in range(1, m):
        if pst[i, cv2.CC_STAT_AREA] >= 40:
            keep[plab == i] = 0
    if keep.sum() / 255 < 0.05 * h * w:
        return None
    # photo backgrounds that aren't plain (gradients, shadows) leave big background-coloured
    # areas on the figure: such figures keep their normal still picture instead
    kept = keep > 0
    if (dist[kept] <= 22).mean() > 0.22:
        return None
    alpha = cv2.GaussianBlur(keep, (3, 3), 0)
    ys, xs = np.where(keep > 0)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgba = np.dstack([bgr, alpha])[y0:y1, x0:x1]
    s = H_PX / rgba.shape[0]
    return cv2.resize(rgba, (max(1, int(round(rgba.shape[1] * s))), H_PX), interpolation=cv2.INTER_CUBIC)


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
        if img is not None and "--debug" in sys.argv:
            (OUT / "_raw").mkdir(exist_ok=True)
            cv2.imwrite(str(OUT / "_raw" / f"{no}.png"), img)
        res = cutout(img) if img is not None else None
        if res is None:
            index[no] = None
            failed += 1
            continue
        cv2.imwrite(str(OUT / f"{no}.webp"), res, [cv2.IMWRITE_WEBP_QUALITY, 82])
        index[no] = {"r": round(res.shape[1] / res.shape[0], 4)}
        ok += 1
    idx_path.write_text(json.dumps(index, indent=1, sort_keys=True))
    print(f"Kész: {ok} figura, {failed} sikertelen.")


if __name__ == "__main__":
    main()
