#!/usr/bin/env python3
"""Cut the minifigures out of their BrickLink photo (transparent WebP) for the display-plate cards.

Background removal uses BiRefNet (general), an open segmentation model run with onnxruntime,
so shadows, grey gradients and photographed backgrounds are removed while white legs on a
white background are kept.

Output: assets/figs/<no>.webp and assets/figs/index.json
        {"sw0314": {"r": 0.62, "fw": 0.48, "fx": 0.5}}
        r = width / height, fw / fx = width and centre of the feet (fractions of the width)
Only new figures are processed unless --force (or --only sw0001,sw0002).
Requires: pip install onnxruntime numpy pillow opencv-python-headless
"""
import json, os, sys, urllib.request
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "figs"
INV = ROOT / "data" / "inventory.json"
H_PX = 300  # output height
MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/BiRefNet-general-epoch_244.onnx"
MODEL = Path(os.environ.get("FIG_MODEL", Path.home() / ".cache" / "matthewsfigs" / "birefnet-general.onnx"))
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)


def fetch(no):
    url = f"https://img.bricklink.com/ItemImage/MN/0/{no}.png"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 matthewsfigs.hu"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return Image.open(__import__("io").BytesIO(r.read())).convert("RGB")
    except Exception:
        return None


def session():
    if not MODEL.exists():
        MODEL.parent.mkdir(parents=True, exist_ok=True)
        print("Modell letöltése…")
        urllib.request.urlretrieve(MODEL_URL, MODEL)
    so = ort.SessionOptions()
    return ort.InferenceSession(str(MODEL), so, providers=["CPUExecutionProvider"])


def predict(sess, img):
    """Soft foreground mask (0..255) for an RGB image, via a square, border-coloured canvas."""
    w, h = img.size
    s = max(w, h)
    arr = np.array(img)
    border = np.concatenate([arr[0], arr[-1], arr[:, 0], arr[:, -1]])
    bgc = tuple(int(v) for v in np.median(border, axis=0))
    sq = Image.new("RGB", (s, s), bgc)
    ox, oy = (s - w) // 2, (s - h) // 2
    sq.paste(img, (ox, oy))
    x = (np.array(sq.resize((1024, 1024), Image.LANCZOS)).astype(np.float32) / 255.0 - MEAN) / STD
    out = sess.run(None, {sess.get_inputs()[0].name: x.transpose(2, 0, 1)[None].astype(np.float32)})[0][0, 0]
    out = 1 / (1 + np.exp(-out))
    m = np.array(Image.fromarray((out * 255).clip(0, 255).astype(np.uint8)).resize((s, s), Image.LANCZOS))
    return m[oy:oy + h, ox:ox + w]


def clean(mask):
    """Hard-ish alpha: keep the figure and parts attached to it, drop spare heads / specks in the corners."""
    a = mask.astype(np.float32) / 255.0
    a = np.clip((a - 0.25) / 0.5, 0, 1)                     # firm up the soft edge, drop faint haze
    solid = (a > 0.5).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(solid, 8)
    if n <= 1:
        return None
    big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    bx, by, bw, bh = st[big, :4]
    pad = 0.04 * max(bw, bh)
    keep = np.zeros_like(solid)
    for i in range(1, n):
        x, y, w, h, area = st[i]
        inside = x + w > bx - pad and x < bx + bw + pad and y + h > by - pad and y < by + bh + pad
        if i == big or (inside and area >= 0.004 * st[big, cv2.CC_STAT_AREA]):
            keep[lab == i] = 1
    keep = cv2.dilate(keep, np.ones((3, 3), np.uint8))       # keep the antialiased rim
    return (a * keep * 255).astype(np.uint8)


def tidy(alpha):
    """Remove the spare head / small extra pieces BrickLink photos often show in a top corner."""
    H, W = alpha.shape
    solid = (alpha > 128).astype(np.uint8)
    k = max(2, round(H * 0.012))
    er = cv2.erode(solid, np.ones((k, k), np.uint8))          # break thin contacts to the figure
    n, lab, st, cen = cv2.connectedComponentsWithStats(er, 8)
    if n <= 2:
        return alpha, 0
    big = 1 + int(np.argmax(st[1:, cv2.CC_STAT_AREA]))
    bx, by, bw, bh = st[big, :4]
    drop = np.zeros_like(solid); nd = 0
    for i in range(1, n):
        if i == big: continue
        x, y, w, h, area = st[i]; cx, cy = cen[i]
        small = area < 0.2 * st[big, cv2.CC_STAT_AREA]
        top = cy < by + 0.38 * bh
        side = cx < bx + 0.22 * bw or cx > bx + 0.78 * bw
        tiny = area < 0.002 * st[big, cv2.CC_STAT_AREA]
        if (small and top and side) or tiny:
            drop[lab == i] = 1; nd += 1
    if not nd:
        return alpha, 0
    drop = cv2.dilate(drop, np.ones((k * 2 + 3, k * 2 + 3), np.uint8))
    # only remove what isn't the main body (main body re-grown from the eroded core)
    main = cv2.dilate((lab == big).astype(np.uint8), np.ones((k * 2 + 3, k * 2 + 3), np.uint8))
    out = alpha.copy(); out[(drop == 1) & (main == 0)] = 0
    # leftovers of the dropped piece that aren't connected to the figure any more
    s2 = (out > 128).astype(np.uint8); n2, l2, st2, _ = cv2.connectedComponentsWithStats(s2, 8)
    if n2 > 2:
        b2 = 1 + int(np.argmax(st2[1:, cv2.CC_STAT_AREA]))
        for j in range(1, n2):
            if j != b2 and st2[j, cv2.CC_STAT_AREA] < 0.01 * st2[b2, cv2.CC_STAT_AREA]:
                out[l2 == j] = 0
    return out, nd


def feet(alpha):
    h, w = alpha.shape
    cols = np.where((alpha[int(h * 0.94):] > 128).any(axis=0))[0]
    if not len(cols):
        return {}
    x0, x1 = int(cols.min()), int(cols.max()) + 1
    return {"fw": round((x1 - x0) / w, 4), "fx": round((x0 + x1) / 2 / w, 4)}


def cutout(sess, img):
    alpha = clean(predict(sess, img))
    if alpha is not None:
        alpha, _ = tidy(alpha)
    if alpha is None or (alpha > 128).sum() < 0.04 * alpha.size:
        return None
    ys, xs = np.where(alpha > 20)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    rgba = np.dstack([np.array(img), alpha])[y0:y1, x0:x1]
    s = H_PX / rgba.shape[0]
    im = Image.fromarray(rgba, "RGBA").resize((max(1, round(rgba.shape[1] * s)), H_PX), Image.LANCZOS)
    return im


def main():
    force = "--force" in sys.argv
    only = next((a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None)
    OUT.mkdir(parents=True, exist_ok=True)
    idx_path = OUT / "index.json"
    index = json.loads(idx_path.read_text()) if idx_path.exists() else {}
    figs = sorted({i["no"] for i in json.loads(INV.read_text())["items"] if i["type"] == "MINIFIG"})
    todo = [n for n in figs if (only and n in only) or (not only and (force or n not in index))]
    if not todo:
        print("Nincs új figura.")
        return
    sess = session()
    ok = failed = 0
    for no in todo:
        img = fetch(no)
        res = cutout(sess, img) if img is not None else None
        if res is None:
            index[no] = None
            failed += 1
            continue
        res.save(OUT / f"{no}.webp", "WEBP", quality=86, method=6)
        a = np.array(res)[:, :, 3]
        index[no] = {"r": round(res.width / res.height, 4), **feet(a)}
        ok += 1
    idx_path.write_text(json.dumps(index, indent=1, sort_keys=True))
    print(f"Kész: {ok} figura, {failed} sikertelen.")


if __name__ == "__main__":
    main()
