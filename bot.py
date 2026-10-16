"""Paylaşım mantığı: haberi seç, karusel/kart üret, Instagram'a gönder. Panel (app.py) ve GitHub (tur.py) kullanır."""

import datetime as dt
import os
import shutil
import threading

import haber
import kart
import karusel
import ozet
import paylas

KOK = haber.KOK
GORSEL = os.path.join(KOK, "data", "gorsel")
os.makedirs(GORSEL, exist_ok=True)
PAYLASIM_KILIDI = threading.Lock()


def simdi():
    return dt.datetime.now(haber.TR)


def hazirla(h, duzenleme=None):
    """Haberin tam metnini okuyup karusel (bilgi azsa tek kart) üretir. (görsel yolları, açıklama, haber) döndürür."""
    cfg = haber.ayar()
    z = ozet.zenginlestir(h)
    if duzenleme:
        z.update({k: v.strip() for k, v in duzenleme.items() if k in ("baslik", "ozet", "kanca") and v.strip()})
    klasor = os.path.join(GORSEL, h["id"])
    shutil.rmtree(klasor, ignore_errors=True)
    os.makedirs(klasor)
    if z["slaytlar"]:
        yollar = karusel.karusel(z, cfg["marka"], cfg["kullanici_adi"], klasor)
    else:
        yollar = [kart.ciz_kart(z, cfg["marka"], cfg["kullanici_adi"], os.path.join(klasor, "01.jpg"))]
    return yollar, kart.aciklama(z, cfg["hashtagler"], karusel=len(yollar) > 1), z


def bugun_paylasilan(d):
    bugun = simdi().date().isoformat()
    return [h for h in d["haberler"].values() if h.get("paylasildi", "").startswith(bugun)]


def haberi_paylas(hid, duzenleme=None, kim="elle"):
    """Tek bir haberi paylaşır. Aynı anda iki paylaşım olmasın diye kilitli."""
    with PAYLASIM_KILIDI:
        cfg = haber.ayar()
        d = haber.durum_oku()
        h = d["haberler"].get(hid)
        if not h:
            raise RuntimeError("Haber bulunamadı")
        if h.get("paylasildi"):
            raise RuntimeError("Bu haber zaten paylaşıldı")
        if h.get("tekrar_of") and d["haberler"].get(h["tekrar_of"], {}).get("paylasildi"):
            raise RuntimeError("Bu haberin bir benzeri zaten paylaşıldı")
        yollar, metin, z = hazirla(h, duzenleme)
        if cfg.get("deneme_modu"):
            ig_id = "deneme"
        else:
            ig_id = paylas.paylas(yollar, metin, cfg)
        with haber.KILIT:
            d = haber.durum_oku()
            h2 = d["haberler"][hid]
            h2.update({"durum": "paylasildi", "paylasildi": simdi().isoformat(), "ig_id": ig_id,
                       "slayt": len(yollar), "kanca": z["kanca"]})
            # aynı olayın diğer sitelerdeki kopyaları da kapansın
            for x in d["haberler"].values():
                if x.get("tekrar_of") == hid:
                    x["durum"] = "tekrar"
            on = "[DENEME] " if cfg.get("deneme_modu") else ""
            tur = f"{len(yollar)} slaytlık karusel" if len(yollar) > 1 else "tek kart"
            haber.kaydet(d, f"{on}Paylaşıldı ({kim}, {tur}): {h['kaynak']} · {h['baslik'][:70]}")
            haber.durum_yaz(d)
        return ig_id


def otomatik_sec(d, cfg):
    o = cfg["otomatik"]
    sinir = simdi() - dt.timedelta(minutes=o["haber_en_eski_dakika"])
    adaylar = [h for h in d["haberler"].values() if h["durum"] == "yeni" and not h.get("tekrar_of")
               and dt.datetime.fromisoformat(h["zaman"]) >= sinir]
    if o.get("sadece_oncelikli"):
        adaylar = [h for h in adaylar if h["oncelikli"]]
    # önce öncelikli haberler, sonra birden fazla sitenin verdiği haberler, sonra en yenisi
    adaylar.sort(key=lambda h: (h["oncelikli"], len(h.get("diger_kaynaklar", [])), h["zaman"]), reverse=True)
    return adaylar[0] if adaylar else None


def otomatik_tur(zorla=False):
    """Kurallar izin veriyorsa sıradaki haberi paylaşır. zorla=True: paneldeki otomatik anahtarına bakma (GitHub)."""
    cfg = haber.ayar()
    o = cfg["otomatik"]
    d = haber.durum_oku()
    if not (zorla or d.get("otomatik")):
        return
    sa = simdi().hour
    bas, son = o.get("sessiz_saatler", [0, 0])
    if bas <= sa < son:
        return
    paylasilan = bugun_paylasilan(d)
    if len(paylasilan) >= o["gunluk_en_fazla"]:
        return
    tum = [h["paylasildi"] for h in d["haberler"].values() if h.get("paylasildi")]
    if tum and simdi() - dt.datetime.fromisoformat(max(tum)) < dt.timedelta(minutes=o["iki_paylasim_arasi_dakika"]):
        return
    h = otomatik_sec(d, cfg)
    if not h:
        return
    try:
        haberi_paylas(h["id"], kim="otomatik")
    except Exception as e:
        with haber.KILIT:
            d = haber.durum_oku()
            d["haberler"][h["id"]]["durum"] = "hata"
            d["haberler"][h["id"]]["hata"] = str(e)
            haber.kaydet(d, f"Otomatik paylaşım başarısız: {e}")
            haber.durum_yaz(d)
