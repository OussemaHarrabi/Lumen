"""Vérifie la pile déployée sur Render : presets, métriques, recalage."""
import time, json
import httpx

BASE = "https://lumen-api-lhdx.onrender.com/api"
s = httpx.Client(base_url=BASE, timeout=120)
presets = {p["id"]: p for p in s.get("/presets").json()}

def asset(slug, part=None):
    url = f"/demos/{slug}/asset" + (f"?part={part}" if part else "")
    r = s.post(url); r.raise_for_status(); return r.json()

def analyse(slug, preset_id, has_ref):
    img = asset(slug)
    body = {"asset_id": img["id"], "steps": presets[preset_id]["steps"]}
    if has_ref:
        body["reference_mask_id"] = asset(slug, "mask")["id"]
    r = s.post("/analyses", json=body); r.raise_for_status()
    a = r.json(); t0 = time.time()
    while True:
        st = s.get(f"/analyses/{a['id']}").json()
        if st["status"] in ("done", "failed"):
            break
        if time.time() - t0 > 120:
            return {"preset": preset_id, "erreur": "délai"}
        time.sleep(1)
    if st["status"] == "failed":
        return {"preset": preset_id, "erreur": st.get("error")}
    res = s.get(f"/analyses/{a['id']}/result").json()
    m = res.get("metrics") or {}
    return {"preset": preset_id, "dice": m.get("dice"), "iou": m.get("iou"),
            "attendu": presets[preset_id].get("expected"), "ms": res.get("total_ms")}

for slug, pid, ref in [("endoscopie-cours", "watershed", True), ("endoscopie-cours", "kmeans", True),
                       ("endoscopie-cours", "chan-vese", True), ("endoscopie-unet", "unet", True),
                       ("mammaire-busi", "otsu", True)]:
    print(json.dumps(analyse(slug, pid, ref), ensure_ascii=False))

# Recalage : paire FIRE, registre ANHIR fourni par le cours.
demo = json.load(open("apps/api/app/demos/retines-fire/demo.json"))
fixed, moving = asset("retines-fire", "fixed"), asset("retines-fire", "moving")
for methode in ("homography", "affine"):
    r = s.post("/registrations", json={"fixed_asset_id": fixed["id"], "moving_asset_id": moving["id"], "method": methode})
    r.raise_for_status(); reg = r.json()
    pts = demo["landmarks"]
    r = s.post(f"/registrations/{reg['id']}/landmarks", json={"points": [[p[0], p[1]] for p in pts]})
    print(methode, r.status_code, json.dumps(r.json().get("metrics"), ensure_ascii=False)[:220])
    for vue in ("overlay", "checkerboard"):
        img = s.get(f"/registrations/{reg['id']}/{vue}.png")
        print(" ", vue, img.status_code, len(img.content), "octets")
