"""Haber sitelerinin RSS/Atom akışlarını çeker, aynı haberi (farklı sitelerden de olsa) bir kez tutar."""

import datetime as dt
import email.utils
import hashlib
import html
import json
import os
import re
import threading
import xml.etree.ElementTree as ET

import requests

KOK = os.path.dirname(os.path.abspath(__file__))
DURUM = os.path.join(KOK, "data", "durum.json")
TR = dt.timezone(dt.timedelta(hours=3))
KILIT = threading.RLock()
TARAYICI = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

# Benzerlik karşılaştırmasında anlam taşımayan kelimeler
DOLGU = set("""son dakika flas flaş haber haberi haberleri acil canli canlı video foto galeri ve ile de da bu bir icin için
ne mi mı mu mü ki o en daha cok çok gibi kadar sonra once önce var yok olan oldu olarak dedi açıkladı acikladi""".split())


def ayar():
    with open(os.path.join(KOK, "config.json"), encoding="utf-8") as f:
        return json.load(f)


def durum_oku():
    with KILIT:
        if not os.path.exists(DURUM):
            return {"haberler": {}, "kayit": [], "otomatik": False}
        with open(DURUM, encoding="utf-8") as f:
            return json.load(f)


def durum_yaz(d):
    with KILIT:
        tmp = DURUM + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        os.replace(tmp, DURUM)


def kaydet(d, mesaj):
    zaman = dt.datetime.now(TR).strftime("%d.%m %H:%M:%S")
    d["kayit"] = ([f"{zaman}  {mesaj}"] + d.get("kayit", []))[:200]
    print(zaman, mesaj, flush=True)


# ---------- metin ----------

def temizle(metin):
    metin = re.sub(r"<[^>]+>", " ", html.unescape(metin or ""))
    return re.sub(r"\s+", " ", metin).strip()


def kucult(metin):
    return metin.replace("İ", "i").replace("I", "ı").lower()


def kelimeler(baslik):
    """Başlığın kelime kökleri: Türkçe ekler karşılaştırmayı bozmasın diye ilk 5 harf."""
    s = kucult(baslik)
    s = s.translate(str.maketrans("çğıöşüâî", "cgiosuai"))
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    dolgu = {w.translate(str.maketrans("çğıöşü", "cgiosu")) for w in DOLGU}
    return {w[:5] for w in s.split() if len(w) > 1 and w not in dolgu}


def benzer(a, b):
    if not a or not b:
        return False
    ortak = len(a & b)
    return ortak / len(a | b) >= 0.40 or (min(len(a), len(b)) >= 3 and ortak / min(len(a), len(b)) >= 0.60)


def ozet_kisalt(ozet, baslik, sinir=280):
    ozet = temizle(ozet)
    if not ozet or kelimeler(ozet) <= kelimeler(baslik) | {""}:  # özet başlığın tekrarıysa boş bırak
        return ""
    if len(ozet) <= sinir:
        return ozet
    kes = ozet[:sinir]
    nokta = max(kes.rfind(". "), kes.rfind("! "), kes.rfind("? "))
    return kes[:nokta + 1] if nokta > 80 else kes.rsplit(" ", 1)[0] + "…"


# ---------- akış okuma ----------

def tarih(metin):
    metin = (metin or "").strip()
    if not metin:
        return dt.datetime.now(TR)
    try:
        t = dt.datetime.fromisoformat(metin.replace("Z", "+00:00"))
    except ValueError:
        try:
            t = email.utils.parsedate_to_datetime(metin.replace(" Z", " +0000"))
        except (TypeError, ValueError):
            return dt.datetime.now(TR)
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t.astimezone(TR)


def yerel(el):
    return el.tag.rsplit("}", 1)[-1]


def cocuk(el, ad):
    return next((c for c in el if yerel(c) == ad), None)


def metni(el, ad):
    c = cocuk(el, ad)
    return (c.text or "") if c is not None else ""


def xml_coz(icerik):
    try:
        return ET.fromstring(icerik)
    except ET.ParseError:
        metin = icerik.decode("utf-8", errors="ignore")
        metin = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", metin)
        metin = re.sub(r"&(?!(?:[a-zA-Z0-9]+|#\d+|#x[0-9a-fA-F]+);)", "&amp;", metin)
        return ET.fromstring(metin.encode("utf-8"))


def akis_oku(kaynak):
    # Tarayıcı kimliği: bazı siteler (NTV) bot kimliğine sunucu IP'lerinden 403 veriyor
    r = requests.get(kaynak["url"], timeout=20, headers={"User-Agent": TARAYICI})
    r.raise_for_status()
    kok = xml_coz(r.content)
    girdiler = [e for e in kok.iter() if yerel(e) in ("item", "entry")]
    sonuc = []
    for e in girdiler:
        baslik = re.sub(r"^(son dak[iİı]ka|flaş|flas)\W*", "", temizle(metni(e, "title")), flags=re.I)
        baslik = baslik[:1].upper() + baslik[1:]
        link = metni(e, "link").strip()
        if not link:  # Atom: <link href="...">
            l = cocuk(e, "link")
            link = l.get("href", "") if l is not None else ""
        if not baslik or not link:
            continue
        ozet = metni(e, "description") or metni(e, "summary")
        zaman = metni(e, "pubDate") or metni(e, "published") or metni(e, "updated")
        temiz_link = link.split("?at_medium")[0]
        sonuc.append({
            "id": hashlib.sha1(temiz_link.encode()).hexdigest()[:12],
            "kaynak": kaynak["ad"],
            "baslik": baslik,
            "ozet": ozet_kisalt(ozet, baslik),
            "link": temiz_link,
            "zaman": tarih(zaman).isoformat(),
        })
    return sonuc


def engelli(h, cfg):
    s = kucult(h["baslik"])
    return any(k in s for k in cfg.get("engellenen_kelimeler", []))


def oncelikli(h, cfg):
    s = " " + kucult(h["baslik"] + " " + h["ozet"]) + " "
    return any(re.search(r"\b" + re.escape(k), s) for k in cfg["otomatik"].get("oncelikli_kelimeler", []))


def guncelle():
    """Tüm kaynakları çeker; yeni haberleri ekler, tekrarları ilk gelen habere bağlar. Yeni haber sayısını döndürür."""
    cfg = ayar()
    gelen, hatalar = [], []
    for k in cfg["kaynaklar"]:
        try:
            gelen += akis_oku(k)
        except Exception as e:
            hatalar.append(f"{k['ad']}: {e}")
    if cfg.get("telegram_kanallari"):
        import telegram_kaynak
        for tk in cfg["telegram_kanallari"]:
            try:
                gelen += telegram_kaynak.kanal_oku(tk)
            except Exception as e:
                hatalar.append(f"Telegram ({tk.get('kullanici', '')}): {e}")

    with KILIT:
        d = durum_oku()
        hab = d["haberler"]
        simdi = dt.datetime.now(TR)
        # 3 günden eski haberleri unut (paylaşılanların kaydı kalır ki tekrar gelmesin)
        for i in [i for i, h in hab.items() if simdi - dt.datetime.fromisoformat(h["zaman"]) > dt.timedelta(days=3)]:
            del hab[i]

        yeni = 0
        gelen.sort(key=lambda h: h["zaman"])  # önce yayımlanan "asıl" haber olsun
        for h in gelen:
            if h["id"] in hab:
                continue
            if simdi - dt.datetime.fromisoformat(h["zaman"]) > dt.timedelta(days=2):
                continue
            kel = kelimeler(h["baslik"])
            yakin = dt.datetime.fromisoformat(h["zaman"]) - dt.timedelta(hours=36)
            asil = next((x for x in hab.values() if not x.get("tekrar_of")
                         and dt.datetime.fromisoformat(x["zaman"]) >= yakin
                         and benzer(kel, set(x["kelimeler"]))), None)
            h["kelimeler"] = sorted(kel)
            h["durum"] = "engelli" if engelli(h, cfg) else "yeni"
            h["oncelikli"] = oncelikli(h, cfg)
            if asil:
                h["tekrar_of"] = asil["id"]
                h["durum"] = "tekrar"
                if h["kaynak"] not in asil.setdefault("diger_kaynaklar", []) and h["kaynak"] != asil["kaynak"]:
                    asil["diger_kaynaklar"].append(h["kaynak"])
            else:
                yeni += 1
            hab[h["id"]] = h
        for hata in hatalar:
            kaydet(d, "Akış okunamadı: " + hata)
        if yeni:
            kaydet(d, f"{yeni} yeni haber")
        durum_yaz(d)
    return yeni


if __name__ == "__main__":
    print(guncelle(), "yeni haber")
    d = durum_oku()
    for h in sorted(d["haberler"].values(), key=lambda h: h["zaman"], reverse=True)[:25]:
        print(f"{h['zaman'][11:16]} {h['kaynak']:<10} {h['durum']:<7} {'*' if h['oncelikli'] else ' '} {h['baslik'][:90]}")
