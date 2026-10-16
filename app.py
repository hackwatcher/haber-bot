"""Haber paneli: http://localhost:5055  ·  Arka planda akışları çeker, otomatik mod açıksa kendisi paylaşır."""

import os
import threading
import time
import warnings

warnings.filterwarnings("ignore")

from flask import Flask, jsonify, render_template, request, send_file  # noqa: E402

import haber  # noqa: E402
from bot import GORSEL, hazirla, haberi_paylas, otomatik_tur, bugun_paylasilan  # noqa: E402

app = Flask(__name__)


def dongu():
    while True:
        try:
            haber.guncelle()
            otomatik_tur()
        except Exception as e:
            print("Döngü hatası:", e, flush=True)
        time.sleep(max(1, haber.ayar()["otomatik"]["kontrol_dakika"]) * 60)


# ---------- web ----------

@app.get("/")
def panel():
    return render_template("panel.html")


@app.get("/api/durum")
def api_durum():
    cfg = haber.ayar()
    d = haber.durum_oku()
    liste = [h for h in d["haberler"].values() if h["durum"] != "tekrar"]
    liste.sort(key=lambda h: h["zaman"], reverse=True)
    for h in liste:
        h.pop("kelimeler", None)
    return jsonify({
        "haberler": liste[:150],
        "kayit": d.get("kayit", [])[:40],
        "otomatik": d.get("otomatik", False),
        "deneme": cfg.get("deneme_modu", False),
        "bugun": len(bugun_paylasilan(d)),
        "gunluk_en_fazla": cfg["otomatik"]["gunluk_en_fazla"],
        "aralik": cfg["otomatik"]["iki_paylasim_arasi_dakika"],
    })


@app.post("/api/otomatik")
def api_otomatik():
    with haber.KILIT:
        d = haber.durum_oku()
        d["otomatik"] = bool(request.json.get("acik"))
        haber.kaydet(d, "Otomatik mod " + ("AÇILDI" if d["otomatik"] else "kapatıldı"))
        haber.durum_yaz(d)
    return jsonify(ok=True)


@app.post("/api/yenile")
def api_yenile():
    return jsonify(yeni=haber.guncelle())


@app.post("/api/onizle/<hid>")
def api_onizle(hid):
    d = haber.durum_oku()
    yollar, metin, z = hazirla(dict(d["haberler"][hid]), request.json or {})
    t = int(time.time())
    return jsonify(slaytlar=[f"/gorsel/{hid}/{os.path.basename(y)}?t={t}" for y in yollar], aciklama=metin,
                   kanca=z["kanca"], baslik=z["baslik"])


@app.get("/gorsel/<hid>/<ad>")
def gorsel(hid, ad):
    return send_file(os.path.join(GORSEL, os.path.basename(hid), os.path.basename(ad)), mimetype="image/jpeg",
                     max_age=0)


@app.post("/api/paylas/<hid>")
def api_paylas(hid):
    try:
        ig_id = haberi_paylas(hid, request.json or {})
        return jsonify(ok=True, id=ig_id)
    except Exception as e:
        return jsonify(ok=False, hata=str(e)), 400


@app.post("/api/gizle/<hid>")
def api_gizle(hid):
    with haber.KILIT:
        d = haber.durum_oku()
        d["haberler"][hid]["durum"] = "gizli"
        haber.durum_yaz(d)
    return jsonify(ok=True)


if __name__ == "__main__":
    threading.Thread(target=dongu, daemon=True).start()
    print("Panel: http://localhost:5055", flush=True)
    app.run(host="127.0.0.1", port=5055, debug=False, threaded=True)
