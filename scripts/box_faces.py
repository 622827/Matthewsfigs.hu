#!/usr/bin/env python3
"""Cut the BrickLink box photos into flat box faces for the 3D boxes.

BrickLink's "original box" photo (ItemImage/ON) shows the box at an angle:
front, one side and the top are visible. The silhouette of such a box is a
hexagon; its hidden corner G (where front, side and top meet) follows from the
hexagon, and each visible face is then perspective-corrected to a rectangle.

Output (only for sets that don't have faces yet, unless --force):
    assets/boxes/<no>-front.jpg, <no>-side.jpg, <no>-top.jpg
    assets/boxes/index.json   {"75342-1": {"w":1, "h":0.68, "d":0.22, "side":"left"}, ...}

Requires: pip install opencv-python-headless numpy
"""
import json, sys, urllib.request
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "boxes"
INV = ROOT / "data" / "inventory.json"
FRONT_PX = 420  # width of the front face image

# Box photos the automatic detection can't read (cropped or shot without the top visible):
# corners picked by hand on the 800px BrickLink photo. "h" and "d" are the box proportions.
OVERRIDES = {
    "75379-1": {"front": [[50, 28], [404, 12], [402, 548], [58, 598]],
                "side": [[2, 18], [50, 28], [58, 598], [5, 492]],
                "h": 1.6, "d": 0.3},
}


def from_override(img, o):
    fw = FRONT_PX
    fh = int(round(fw * o["h"]))
    dw = int(round(fw * o["d"]))
    front = warp(img, np.array(o["front"], float), fw, fh)
    side = warp(img, np.array(o["side"], float), dw, fh)
    # no top visible on the photo: use the side panel turned on its back
    top = cv2.resize(cv2.rotate(side, cv2.ROTATE_90_CLOCKWISE), (fw, dw), interpolation=cv2.INTER_AREA)
    return {"front": front, "side": side, "top": top,
            "meta": {"w": 1.0, "h": o["h"], "d": o["d"], "side": "left"}}


def fetch(no):
    url = f"https://img.bricklink.com/ItemImage/ON/0/{no}.png"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 matthewsfigs.hu"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = np.frombuffer(r.read(), np.uint8)
    except Exception:
        return None
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    return img


def silhouette(img):
    bgr, a = img[:, :, :3], img[:, :, 3]
    not_white = (bgr.min(axis=2) < 235)
    mask = ((a > 20) & not_white).astype(np.uint8) * 255
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8), iterations=2)
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(c) < 0.15 * img.shape[0] * img.shape[1]:
        return None
    return cv2.convexHull(c)


def hexagon(hull):
    peri = cv2.arcLength(hull, True)
    for eps in np.linspace(0.005, 0.06, 56):
        poly = cv2.approxPolyDP(hull, eps * peri, True)
        if len(poly) == 6:
            return poly.reshape(6, 2).astype(np.float64)
        if len(poly) < 6:
            break
    return None


def faces_from_hexagon(V):
    """Return (G, quads): G is the visible corner where front, side and top meet,
    quads are the 3 visible faces as (Vk, Vk+1, Vk+2, G) in cyclic order."""
    size = np.linalg.norm(V.max(axis=0) - V.min(axis=0))
    cands = []
    for parity in (0, 1):
        ks = [parity, parity + 2, parity + 4]
        pts = [V[k % 6] + V[(k + 2) % 6] - V[(k + 1) % 6] for k in ks]
        G = np.mean(pts, axis=0)
        err = max(np.linalg.norm(c - G) for c in pts)
        quads = [[V[k % 6], V[(k + 1) % 6], V[(k + 2) % 6], G] for k in ks]
        cands.append((err, G, quads))
    good = [c for c in cands if c[0] <= 0.12 * size]
    if not good:
        return None
    # Both alternating triples give a consistent inner point: the visible top-front corner
    # and the hidden bottom-back corner. The camera looks from above, so take the higher one.
    err, G0, quads = min(good, key=lambda c: c[1][1])
    parity = next(p for p in (0, 1) if np.allclose(quads[0][0], V[p]))
    G = refine_corner(V, parity, G0)
    quads = [[q[0], q[1], q[2], G] for q in quads]
    return G, quads


def _h(p):
    return np.array([p[0], p[1], 1.0])


def refine_corner(V, parity, G0):
    """Perspective-correct position of the inner corner.

    The edge from G to a neighbouring hull vertex Vk is parallel (in 3D) to the hull
    edges Vk+1–Vk+2 and Vk-2–Vk-1, so it points at their vanishing point. G is where
    the three such lines meet (least squares)."""
    lines = []
    for k in (parity, parity + 2, parity + 4):
        l1 = np.cross(_h(V[(k + 1) % 6]), _h(V[(k + 2) % 6]))
        l2 = np.cross(_h(V[(k - 2) % 6]), _h(V[(k - 1) % 6]))
        vp = np.cross(l1, l2)
        line = np.cross(_h(V[k % 6]), vp)
        n = np.linalg.norm(line[:2])
        if n < 1e-9:
            return G0
        lines.append(line / n)
    A = np.array(lines)
    _, _, vt = np.linalg.svd(A)
    x = vt[-1]
    if abs(x[2]) < 1e-9:
        return G0
    G = x[:2] / x[2]
    size = np.linalg.norm(V.max(axis=0) - V.min(axis=0))
    return G if np.linalg.norm(G - G0) < 0.08 * size else G0


def area(q):
    return abs(cv2.contourArea(np.array(q, np.float32)))


def warp(img, quad_tl_tr_br_bl, w, h, inset=0.025):
    """Perspective-correct one face. The face is cut slightly inside its edges
    (inset) so no background or edge highlight ends up on the border."""
    w, h = int(w), int(h)
    mx, my = max(2.0, inset * w), max(2.0, inset * h)
    src = np.array(quad_tl_tr_br_bl, np.float32)
    dst = np.array([[-mx, -my], [w - 1 + mx, -my], [w - 1 + mx, h - 1 + my], [-mx, h - 1 + my]], np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    bgr = out[:, :, :3].astype(np.float32)
    a = out[:, :, 3:4].astype(np.float32) / 255.0
    flat = (bgr * a + 255 * (1 - a)).astype(np.uint8)  # flatten onto white
    return trim_white(flat)


def trim_white(face, limit=0.08):
    """Cut away near-white rows/columns that are left on the borders, then scale back."""
    h, w = face.shape[:2]
    g = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY).astype(np.float32)
    whiteish = lambda v: (v > 225).mean() > 0.6
    t, b, l, r = 0, h, 0, w
    while t < h * limit and whiteish(g[t, l:r]): t += 1
    while h - b < h * limit and whiteish(g[b - 1, l:r]): b -= 1
    while l < w * limit and whiteish(g[t:b, l]): l += 1
    while w - r < w * limit and whiteish(g[t:b, r - 1]): r -= 1
    if (t, b, l, r) == (0, h, 0, w):
        return face
    return cv2.resize(face[t:b, l:r], (w, h), interpolation=cv2.INTER_CUBIC)


WHY = {}


def fail(reason):
    WHY["last"] = reason
    return None


def analyse(img):
    hull = silhouette(img)
    if hull is None:
        return fail("no-silhouette")
    WHY["hull"] = hull
    V = hexagon(hull)
    if V is None:
        return fail("not-hexagon")
    WHY["hex"] = V
    res = faces_from_hexagon(V)
    if res is None:
        return fail("not-a-box")
    G, quads = res
    quads.sort(key=area, reverse=True)
    front = quads[0]
    # the two other faces share an edge with the front: the one sharing a near-vertical edge is the side
    others = quads[1:]

    def shared(q):  # the non-G vertex of q that is also a front vertex
        for p in (q[0], q[2]):
            if any(np.allclose(p, f) for f in front):
                return p
        return None

    side = top = None
    for q in others:
        p = shared(q)
        if p is None:
            return fail("no-shared-edge")
        d = p - G
        if abs(d[1]) > abs(d[0]):
            side, Ev = q, p
        else:
            top, Ch = q, p
    if side is None or top is None:
        return fail("side/top-missing")
    opp = next(f for f in front if not (np.allclose(f, G) or np.allclose(f, Ev) or np.allclose(f, Ch)))
    if G[1] > Ev[1]:
        return fail("bottom-visible")

    side_is_left = np.mean([p[0] for p in side], axis=0) < G[0]

    # front TL TR BR BL
    if side_is_left:
        fq = [G, Ch, opp, Ev]
    else:
        fq = [Ch, G, Ev, opp]
    # side: the two side vertices not on the front
    s_other = [p for p in (side[0], side[1], side[2]) if not (np.allclose(p, Ev))]
    S1 = min(s_other, key=lambda p: np.linalg.norm(p - G))  # next to G (top-back)
    S2 = max(s_other, key=lambda p: np.linalg.norm(p - G))  # bottom-back
    sq = [S1, G, Ev, S2] if side_is_left else [G, S1, S2, Ev]
    # top: two vertices not on the front
    t_other = [p for p in (top[0], top[1], top[2]) if not np.allclose(p, Ch)]
    T1 = min(t_other, key=lambda p: np.linalg.norm(p - G))  # behind G
    T2 = max(t_other, key=lambda p: np.linalg.norm(p - G))  # behind Ch
    tq = [T1, T2, Ch, G] if side_is_left else [T2, T1, G, Ch]

    W = (np.linalg.norm(fq[0] - fq[1]) + np.linalg.norm(fq[3] - fq[2])) / 2
    H = (np.linalg.norm(fq[0] - fq[3]) + np.linalg.norm(fq[1] - fq[2])) / 2
    # the side is strongly foreshortened; LEGO boxes are roughly 15-35 % as deep as they are wide
    D_seen = (np.linalg.norm(sq[0] - sq[1]) + np.linalg.norm(sq[3] - sq[2])) / 2
    D = float(np.clip(D_seen * 1.7, 0.14 * W, 0.38 * W))
    if W < 80 or H < 60:
        return fail("too-small")

    fw = FRONT_PX
    fh = int(round(fw * H / W))
    dw = max(24, int(round(fw * D / W)))
    return {
        "front": warp(img, fq, fw, fh),
        "side": warp(img, sq, dw, fh),
        "top": warp(img, tq, fw, dw),
        "meta": {"w": 1.0, "h": round(float(H / W), 4), "d": round(float(D / W), 4), "side": "left" if side_is_left else "right"},
    }


def main():
    force = "--force" in sys.argv
    only = [a for a in sys.argv[1:] if not a.startswith("--")]
    OUT.mkdir(parents=True, exist_ok=True)
    idx_path = OUT / "index.json"
    index = json.loads(idx_path.read_text()) if idx_path.exists() else {}
    sets = only or sorted({i["no"] for i in json.loads(INV.read_text())["items"] if i["type"] == "SET"})
    ok = skipped = failed = 0
    for no in sets:
        if no in index and not force:
            skipped += 1
            continue
        img = fetch(no)
        WHY.clear()
        if img is not None and no in OVERRIDES:
            res = from_override(img, OVERRIDES[no])
        else:
            res = analyse(img) if img is not None else fail("no-photo")
        if "--debug" in sys.argv and img is not None:
            dbg = OUT / "_debug"; dbg.mkdir(exist_ok=True)
            vis = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR).copy()
            if "hull" in WHY: cv2.polylines(vis, [WHY["hull"]], True, (0, 0, 255), 2)
            if "hex" in WHY:
                for x, y in WHY["hex"]: cv2.circle(vis, (int(x), int(y)), 7, (255, 0, 0), -1)
            cv2.putText(vis, WHY.get("last", "ok"), (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
            cv2.imwrite(str(dbg / f"{no}.jpg"), vis, [cv2.IMWRITE_JPEG_QUALITY, 70])
            cv2.imwrite(str(dbg / f"{no}-raw.png"), img)
        if not res:
            index[no] = None  # remember: no usable box photo, show the flat set picture
            failed += 1
            print(f"  – {no}: nincs használható dobozfotó ({WHY.get('last')})")
            continue
        for k in ("front", "side", "top"):
            cv2.imwrite(str(OUT / f"{no}-{k}.jpg"), res[k], [cv2.IMWRITE_JPEG_QUALITY, 86])
        index[no] = res["meta"]
        ok += 1
        print(f"  ✓ {no}: {res['meta']}")
    idx_path.write_text(json.dumps(index, indent=1, sort_keys=True))
    print(f"Kész: {ok} új doboz, {failed} sikertelen, {skipped} már megvolt.")


if __name__ == "__main__":
    main()
