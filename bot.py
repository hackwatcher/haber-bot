"""Paylaşım mantığı: haberi seç, karusel/kart üret, Instagram'a gönder. Panel (app.py) ve GitHub (tur.py) kullanır."""

import datetime as dt
import os
import shutil
import threading

import ai_editor
import haber
import kart
import karusel
import ozet
import paylas
import reels

KOK = haber.KOK
GORSEL = os.path.join(KOK, "data", "gorsel")
os.makedirs(GORSEL, exist_ok=True)
PAYLASIM_KILIDI = threading.Lock()


def simdi():
    return dt.datetime.now(haber.TR)


def uygula(z, duz, marka):
    """Haber kaydına dışarıdan verilen düzenlemeleri (kanca, başlık, özet, konu, foto, slaytlar) uygular."""
    if not duz:
        return z
    for k in ("baslik", "ozet", "kanca", "konu", "il", "rakam", "rakam_birim"):
        if k in duz and duz[k] is not None:
            v = duz[k].strip() if isinstance(duz[k], str) else duz[k]
            if v != "" or k in ("il", "rakam", "rakam_birim"):
                z[k] = v
    if duz.get("foto"):
        f = duz["foto"]
        z["foto"] = {"yol": f, "not": f"Temsili görsel · {marka}"} if isinstance(f, str) else f
    if "slaytlar" in duz and duz["slaytlar"] is not None:
        z["slaytlar"] = duz["slaytlar"]
    return z


def hazirla(h, duzenleme=None):
    """Haberin tam metnini okuyup karusel (bilgi azsa tek kart) üretir. (görsel yolları, açıklama, haber) döndürür."""
    cfg = haber.ayar()
    z = ozet.zenginlestir(h)
    if h.get("tg_kanal") or "t.me/" in h.get("link", ""):
        import telegram_kaynak
        tg_foto, tg_video = telegram_kaynak.medya_indir(h, cfg["marka"])
        if tg_foto:
            z["foto"] = tg_foto
        if tg_video:
            z["tg_video"] = tg_video
    if not h.get("duzenleme") and not duzenleme:
        z = ai_editor.zenginlestir_ai(h, z)
    uygula(z, h.get("duzenleme"), cfg["marka"])
    uygula(z, duzenleme, cfg["marka"])
    klasor = os.path.join(GORSEL, h["id"])
    shutil.rmtree(klasor, ignore_errors=True)
    os.makedirs(klasor)
    if z["slaytlar"]:
        yollar = karusel.karusel(z, cfg["marka"], cfg["kullanici_adi"], klasor)
    else:
        yollar = [kart.ciz_kart(z, cfg["marka"], cfg["kullanici_adi"], os.path.join(klasor, "01.jpg"))]
    return yollar, kart.aciklama(z, cfg["hashtagler"], karusel=len(yollar) > 1), z


def ekleri_hazirla(z, yollar, klasor):
    """Aynı haberden Reels videosu ve story görseli. Biri üretilemezse o atlanır, gönderi yine paylaşılır."""
    cfg = haber.ayar()
    video = story = None
    hatalar = []
    try:
        # videoda "KAYDIR" oku ve sayfa numarası olmayan slaytlar
        vs = karusel.karusel(z, cfg["marka"], cfg["kullanici_adi"], klasor, video=True) if z["slaytlar"] else yollar
    except Exception as e:
        vs, _ = yollar, hatalar.append(f"video slaytı: {e}")
    if cfg.get("reels", {}).get("acik", True):
        reels_dosya = os.path.join(klasor, "reels.mp4")
        if z.get("tg_video"):
            try:
                video = reels.gercek_video_reels(z, cfg["marka"], cfg["kullanici_adi"], z["tg_video"], reels_dosya)
            except Exception as e:
                hatalar.append(f"Gerçek video Reels: {e}")
        if not video:
            try:
                spikerli = cfg.get("reels", {}).get("spikerli", True)
                video = reels.video(z, cfg["marka"], cfg["kullanici_adi"], vs, reels_dosya, spikerli=spikerli)
            except Exception as e:
                hatalar.append(f"Reels videosu: {e}")
    if cfg.get("story", {}).get("acik", True):
        sadece_tg = cfg.get("story", {}).get("sadece_telegram", False)
        bu_tg = bool(z.get("tg_kanal") or "t.me/" in z.get("link", ""))
        if not sadece_tg or bu_tg:
            try:
                story = reels.story(z, cfg["marka"], cfg["kullanici_adi"], vs[0], os.path.join(klasor, "story.jpg"))
            except Exception as e:
                hatalar.append(f"story: {e}")
    return video, story, hatalar


def haberi_ozellestir(hid, duzenleme, video_uret=False):
    """Habere özel kanca, görsel ve slaytları durum.json'a kaydeder; karusel (+ isteğe bağlı Reels/story) üretir."""
    with haber.KILIT:
        d = haber.durum_oku()
        h = d["haberler"].get(hid)
        if not h:
            raise RuntimeError("Haber bulunamadı")
        mevcut = dict(h.get("duzenleme") or {})
        mevcut.update(duzenleme)
        h["duzenleme"] = mevcut
        haber.durum_yaz(d)
    yollar, metin, z = hazirla(h)
    video = story = None
    hatalar = []
    if video_uret:
        video, story, hatalar = ekleri_hazirla(z, yollar, os.path.join(GORSEL, h["id"]))
    return {"yollar": yollar, "aciklama": metin, "video": video, "story": story, "hatalar": hatalar, "haber": z}


def bugun_paylasilan(d):
    bugun = simdi().date().isoformat()
    # deneme modundaki sahte paylaşımlar günlük sınırdan yemesin
    return [h for h in d["haberler"].values()
            if h.get("paylasildi", "").startswith(bugun) and h.get("ig_id") != "deneme"]


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
        video, story, hatalar = ekleri_hazirla(z, yollar, os.path.join(GORSEL, h["id"]))

        # Otomatik İlk Yorum & Tartışma Başlatıcı
        ilk_yorum = z.get("yorum_sorusu")
        if not ilk_yorum:
            konu = z.get("konu", "gundem")
            sorular = {
                "ekonomi": "📌 Sizce bu gelişme piyasaları ve fiyatları nasıl etkiler? Yorumlarda buluşalım.",
                "spor": "📌 Bu maç ve transfer hakkındaki görüşünüz nedir? Yorumlarınızı bekliyoruz.",
                "afet": "📌 Bölgedeki vatandaşlarımıza geçmiş olsun dileklerimizi iletiyoruz.",
                "gundem": "📌 Bu konu hakkındaki düşünceleriniz neler? Görüşlerinizi yazın.",
                "dunya": "📌 Dünyada yankı uyandıran bu gelişmeyi nasıl değerlendiriyorsunuz?",
                "asayis": "📌 Sizce bu tür olaylara karşı nasıl tedbirler alınmalı?",
            }
            ilk_yorum = sorular.get(konu, "📌 Bu konu hakkındaki düşünceleriniz neler? Yorumlarda buluşalım.")

        if cfg.get("deneme_modu"):
            sonuc = {"gonderi": "deneme", "reels": "deneme" if video else None, "story": "deneme" if story else None, "yorum": "deneme" if ilk_yorum else None}
        else:
            sonuc = paylas.paylas(yollar, metin, cfg, video=video, story=story, ilk_yorum=ilk_yorum)
        ig_id = sonuc["gonderi"]
        with haber.KILIT:
            d = haber.durum_oku()
            h2 = d["haberler"][hid]
            h2.update({"durum": "paylasildi", "paylasildi": simdi().isoformat(), "ig_id": ig_id,
                       "reels_id": sonuc.get("reels"), "story_id": sonuc.get("story"),
                       "yorum_id": sonuc.get("yorum"),
                       "slayt": len(yollar), "kanca": z["kanca"]})
            # aynı olayın diğer sitelerdeki kopyaları da kapansın
            for x in d["haberler"].values():
                if x.get("tekrar_of") == hid:
                    x["durum"] = "tekrar"
            on = "[DENEME] " if cfg.get("deneme_modu") else ""
            tur = f"{len(yollar)} slaytlık karusel" if len(yollar) > 1 else "tek kart"
            ekler = [ad for ad in ("reels", "story", "yorum") if sonuc.get(ad) and not str(sonuc[ad]).startswith("hata")]
            if ekler:
                tur += " + " + " + ".join(e.capitalize() for e in ekler)
            haber.kaydet(d, f"{on}Paylaşıldı ({kim}, {tur}): {h['kaynak']} · {h['baslik'][:70]}")
            for ad in ("reels", "story", "yorum"):
                if str(sonuc.get(ad) or "").startswith("hata"):
                    hatalar.append(f"{ad}: {sonuc[ad][6:]}")
            for hata in hatalar:
                haber.kaydet(d, "Ek paylaşılamadı: " + hata)
            haber.durum_yaz(d)
        return ig_id


def otomatik_sec(d, cfg):
    o = cfg["otomatik"]
    s_now = simdi()
    sinir_rss = s_now - dt.timedelta(minutes=o["haber_en_eski_dakika"])
    sinir_tg = s_now - dt.timedelta(minutes=o.get("telegram_en_eski_dakika", 1440))
    adaylar = [
        h for h in d["haberler"].values()
        if h["durum"] == "yeni" and not h.get("tekrar_of")
        and dt.datetime.fromisoformat(h["zaman"]) >= (sinir_tg if h.get("tg_kanal") else sinir_rss)
    ]
    if o.get("sadece_oncelikli"):
        adaylar = [h for h in adaylar if h["oncelikli"]]
    # Önce öncelikli kelimeler, sonra bugünkü tüm Telegram haberleri, sonra çoklu kaynaklı RSS, sonra en yenisi
    adaylar.sort(
        key=lambda h: (h["oncelikli"], 1 if h.get("tg_kanal") else 0, len(h.get("diger_kaynaklar", [])), h["zaman"]),
        reverse=True,
    )
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
    tum = [h["paylasildi"] for h in d["haberler"].values() if h.get("paylasildi") and h.get("ig_id") != "deneme"]
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
