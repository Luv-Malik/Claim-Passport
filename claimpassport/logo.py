"""Logo check for image uploads (rule V-4).

The approved logo lives in the Brand Vault (Assets). For every uploaded image we look for it with multi-scale
template matching (OpenCV): the logo is tried at many sizes and the best match is kept. Then we check three things:
  - is the logo there at all,
  - is it big enough (share of the image width), and
  - is it kept away from the edge (margin as a share of the image size).
Limits: this finds the logo when it looks like the uploaded logo file (same shape and colours, any size, not rotated).
It does not find a re-drawn, heavily recoloured, rotated or partly hidden logo. Thresholds are in Vault > Assets > image_rules.
OpenCV is optional: without it the check says "not run" instead of pretending."""
import base64
import io

DEFAULTS = {"logo_threshold": 0.65, "logo_min_width_share": 0.08, "logo_min_margin": 0.02, "logo_required": True}
MAX_LOGO_PX = 600
MAX_IMAGE_SIDE = 1600


def make_asset(data, filename=""):
    """Check an uploaded logo file and turn it into the Vault asset value (a PNG, kept small)."""
    from PIL import Image
    im = Image.open(io.BytesIO(data))
    im.load()
    im = im.convert("RGBA")
    if im.width < 24 or im.height < 24:
        raise ValueError("The logo image is too small to search for (at least 24 x 24 pixels).")
    if max(im.size) > MAX_LOGO_PX:
        f = MAX_LOGO_PX / max(im.size)
        im = im.resize((max(1, int(im.width * f)), max(1, int(im.height * f))), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return {"filename": filename, "png_b64": base64.b64encode(buf.getvalue()).decode(), "width": im.width, "height": im.height}


def logo_bytes(asset):
    return base64.b64decode(asset["png_b64"])


def thresholds(image_rules):
    return {k: (image_rules or {}).get(k, v) for k, v in DEFAULTS.items()}


def check(image_data, logo_png, image_rules=None):
    """Return {"status": found|missing|not_run, ...}. Boxes are in the original image's pixels."""
    try:
        import cv2
        import numpy as np
    except ImportError:
        return {"status": "not_run", "reason": "OpenCV is not installed on this server, so the logo check was skipped."}
    from PIL import Image
    th = thresholds(image_rules)
    img = Image.open(io.BytesIO(image_data)).convert("RGB")
    W, H = img.size
    k = min(1.0, MAX_IMAGE_SIDE / max(W, H))
    small = img.resize((max(1, int(W * k)), max(1, int(H * k)))) if k < 1 else img
    gray = cv2.cvtColor(np.array(small), cv2.COLOR_RGB2GRAY)
    tpl_rgba = Image.open(io.BytesIO(logo_png)).convert("RGBA")
    alpha = np.array(tpl_rgba)[:, :, 3]
    has_alpha = bool((alpha < 250).any())
    bg = Image.new("RGBA", tpl_rgba.size, (255, 255, 255, 255))
    tpl_gray = cv2.cvtColor(np.array(Image.alpha_composite(bg, tpl_rgba).convert("RGB")), cv2.COLOR_RGB2GRAY)
    best = (-1.0, None, 1.0)
    sw = gray.shape[1]
    for frac in np.geomspace(0.03, 0.9, 28):
        tw = int(round(sw * frac))
        th_px = int(round(tpl_gray.shape[0] * tw / tpl_gray.shape[1]))
        if tw < 14 or th_px < 8 or tw >= gray.shape[1] or th_px >= gray.shape[0]:
            continue
        t = cv2.resize(tpl_gray, (tw, th_px), interpolation=cv2.INTER_AREA)
        if float(t.std()) < 2.0:
            continue                                         # a flat template matches everything
        mask = None
        if has_alpha:
            mask = (cv2.resize(alpha, (tw, th_px), interpolation=cv2.INTER_AREA) > 128).astype("uint8") * 255
        try:
            res = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED, mask=mask) if mask is not None else cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
        except cv2.error:
            res = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
        res = np.nan_to_num(res, nan=-1.0, posinf=-1.0, neginf=-1.0)
        _, mx, _, loc = cv2.minMaxLoc(res)
        if mx > best[0]:
            best = (float(mx), loc, tw / sw)
    score, loc, frac = best
    out = {"status": "missing", "score": round(max(score, 0.0), 3), "threshold": th["logo_threshold"], "problems": ["missing"]}
    if loc is None or score < th["logo_threshold"]:
        return out
    tw = frac * W
    x, y = loc[0] / k, loc[1] / k
    w = tw
    h = tpl_gray.shape[0] * tw / tpl_gray.shape[1]
    margin = min(x / W, (W - x - w) / W, y / H, (H - y - h) / H)
    share = w / W
    problems = []
    if share < th["logo_min_width_share"]:
        problems.append("too_small")
    if margin < th["logo_min_margin"]:
        problems.append("near_edge")
    out.update(status="found", box=[int(x), int(y), int(w), int(h)], width_share=round(share, 3),
               margin=round(max(margin, 0.0), 3), problems=problems,
               min_width_share=th["logo_min_width_share"], min_margin=th["logo_min_margin"])
    return out


def raw_findings(res, S):
    """Turn a check result into raw findings for the pipeline."""
    if res.get("status") == "missing":
        return [{"rule_code": "V-4", "span": (0, 0), "confidence": 0.8,
                 "message": f"The approved logo was not found in this image (best match {round(res['score'] * 100)}%, needed {round(res['threshold'] * 100)}%).",
                 "suggestions": [S.note("Add the approved logo", "Place the logo from the Brand Vault in the image, then upload it again."),
                                 S.note("Mark as intentional", "If this image should not carry the logo, keep it as written and say why.")]}]
    if res.get("status") != "found":
        return []
    out = []
    if "too_small" in res["problems"]:
        out.append({"rule_code": "V-4", "span": (0, 0), "confidence": 0.85,
                    "message": f"The logo is too small: it covers {round(res['width_share'] * 100, 1)}% of the image width. "
                               f"At least {round(res['min_width_share'] * 100)}% is needed.",
                    "suggestions": [S.note("Make the logo larger", "Scale the logo up so it is easy to read.")]})
    if "near_edge" in res["problems"]:
        out.append({"rule_code": "V-4", "span": (0, 0), "confidence": 0.85,
                    "message": f"The logo is too close to the edge of the image ({round(res['margin'] * 100, 1)}% clear space; "
                               f"at least {round(res['min_margin'] * 100)}% is needed).",
                    "suggestions": [S.note("Move the logo inwards", "Keep clear space around the logo so it is not cropped.")]})
    return out
