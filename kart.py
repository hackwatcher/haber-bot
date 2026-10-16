"""Haberden 1080x1350 Instagram görseli üretir.

Haber sitelerinin fotoğrafları telifli olduğu için kullanılmaz. Görsel desteği üç yoldan gelir:
konuya göre renk, haberdeki ilin haritası, ya da serbest lisanslı temsili fotoğraf (kaynağı yazılarak).
"""

import datetime as dt
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont, ImageOps

KOK = os.path.dirname(os.path.abspath(__file__))
KALIN = os.path.join(KOK, "fonts", "Montserrat-ExtraBold.ttf")
NORMAL = os.path.join(KOK, "fonts", "Montserrat-Medium.ttf")
ILLER = os.path.join(KOK, "assets", "tr-iller.json")

G, Y = 1080, 1350
KENAR = 80
BEYAZ = (255, 255, 255)
GRI = (170, 178, 190)
SOLUK = (105, 114, 128)

# konu: (etiket, vurgu rengi, zemin, etiket yazı rengi)
KONULAR = {
    "gundem": ("GÜNDEM", (230, 30, 42), (14, 17, 23), BEYAZ),
    "afet": ("AFET", (255, 122, 26), (20, 15, 11), (30, 14, 0)),
    "ekonomi": ("EKONOMİ", (242, 183, 5), (19, 17, 9), (35, 26, 0)),
    "dunya": ("DÜNYA", (55, 138, 221), (10, 16, 28), BEYAZ),
    "spor": ("SPOR", (43, 182, 115), (9, 20, 15), (0, 30, 16)),
    "asayis": ("ASAYİŞ", (139, 124, 246), (16, 14, 26), BEYAZ),
}

AYLAR = "Ocak Şubat Mart Nisan Mayıs Haziran Temmuz Ağustos Eylül Ekim Kasım Aralık".split()


def font(yol, boyut):
    return ImageFont.truetype(yol, boyut)


def buyuk(metin):
    return metin.replace("i", "İ").replace("ı", "I").upper()


def sar(ciz, metin, f, genislik):
    satirlar, satir = [], ""
    for k in metin.split():
        dene = (satir + " " + k).strip()
        if ciz.textlength(dene, font=f) <= genislik:
            satir = dene
        else:
            if satir:
                satirlar.append(satir)
            satir = k
    if satir:
        satirlar.append(satir)
    return satirlar


# ---------- parçalar ----------

def ust_serit(c, marka, konu, ust=0, sayfa=None):
    etiket, vurgu, _, etiket_yazi = konu
    c.rectangle([0, 0, G, 14], fill=vurgu)
    fm = font(KALIN, 44)
    c.text((KENAR, ust + 70), buyuk(marka), font=fm, fill=BEYAZ)
    if sayfa:  # karuselde "2/7"
        c.text((KENAR + c.textlength(buyuk(marka), font=fm) + 24, ust + 78), f"{sayfa[0]}/{sayfa[1]}",
               font=font(NORMAL, 32), fill=SOLUK)
    fe = font(KALIN, 30)
    ew = c.textlength(etiket, font=fe)
    c.rounded_rectangle([G - KENAR - ew - 44, ust + 64, G - KENAR, ust + 122], radius=8, fill=vurgu)
    c.text((G - KENAR - ew - 22, ust + 77), etiket, font=fe, fill=etiket_yazi)


def alt_serit(c, haber, kullanici_adi, vurgu, kaydir=False):
    c.line([KENAR, 1190, G - KENAR, 1190], fill=(45, 50, 60), width=2)
    t = dt.datetime.fromisoformat(haber["zaman"])
    kaynaklar = [haber["kaynak"]] + haber.get("diger_kaynaklar", [])
    fk = font(NORMAL, 30)
    c.text((KENAR, 1222), "Kaynak: " + ", ".join(kaynaklar[:3]), font=fk, fill=GRI)
    c.text((KENAR, 1266), f"{t.day} {AYLAR[t.month - 1]} {t.year} · {t:%H:%M}", font=fk, fill=SOLUK)
    if kaydir:  # karusel kapağı
        kaydir_oku(c, vurgu)
    else:
        ku = font(KALIN, 30)
        c.text((G - KENAR - c.textlength(kullanici_adi, font=ku), 1244), kullanici_adi, font=ku, fill=BEYAZ)


def kaydir_oku(c, vurgu):
    fa = font(KALIN, 36)
    c.text((G - KENAR - 70 - c.textlength("KAYDIR", font=fa), 1236), "KAYDIR", font=fa, fill=BEYAZ)
    x, y = G - KENAR - 50, 1258
    c.line([(x, y), (x + 40, y)], fill=vurgu, width=6)
    c.line([(x + 24, y - 16), (x + 40, y), (x + 24, y + 16)], fill=vurgu, width=6)


def metin_blogu(c, haber, ust, alt, vurgu, en_buyuk=104, ozet_satir=5):
    """Kanca + başlık + özet; alana sığana kadar küçültür, dikeyde ortalar."""
    genislik = G - 2 * KENAR
    kanca = buyuk(haber.get("kanca", ""))
    ozet = haber.get("ozet", "")
    for boyut in range(en_buyuk, 44, -4):
        fb = font(KALIN, boyut)
        bs = sar(c, haber["baslik"], fb, genislik)
        bsat = int(boyut * 1.16)
        fkb = max(36, int(boyut * .55))
        fk = font(KALIN, fkb)
        ks = sar(c, kanca, fk, genislik) if kanca else []
        osb = max(29, min(38, int(boyut * .44)))
        fo = font(NORMAL, osb)
        os_ = sar(c, ozet, fo, genislik - 30) if ozet else []
        if len(os_) > ozet_satir:  # yarım cümle kalmasın
            os_ = os_[:ozet_satir]
            os_[-1] = os_[-1].rstrip(",;:") + "…"
        h = (len(ks) * int(fkb * 1.2) + 28 if ks else 0) + len(bs) * bsat \
            + (len(os_) * int(osb * 1.45) + 40 if os_ else 0)
        if h <= alt - ust:
            break
    y = ust + max(0, (alt - ust - h) // 2)
    if ks:
        c.rectangle([KENAR, y + 6, KENAR + 12, y + len(ks) * int(fkb * 1.2) - 10], fill=vurgu)
        for s in ks:
            c.text((KENAR + 32, y), s, font=fk, fill=vurgu)
            y += int(fkb * 1.2)
        y += 28
    for s in bs:
        c.text((KENAR, y), s, font=fb, fill=BEYAZ)
        y += bsat
    if os_:
        y += 40
        for s in os_:
            c.text((KENAR, y), s, font=fo, fill=GRI)
            y += int(osb * 1.45)


# ---------- harita ----------

def il_haritasi(c, il, kutu, vurgu, zemin):
    with open(ILLER, encoding="utf-8") as f:
        iller = json.load(f)["features"]
    x0, y0, x1, y1 = kutu
    lon0, lon1, lat0, lat1 = 25.6, 44.9, 35.8, 42.2
    k = math.cos(math.radians(39))
    olcek = min((x1 - x0) / ((lon1 - lon0) * k), (y1 - y0) / (lat1 - lat0))
    ox = x0 + ((x1 - x0) - (lon1 - lon0) * k * olcek) / 2
    oy = y0 + ((y1 - y0) - (lat1 - lat0) * olcek) / 2

    def p(lon, lat):
        return ox + (lon - lon0) * k * olcek, oy + (lat1 - lat) * olcek

    def halkalar(geo):
        polys = geo["coordinates"] if geo["type"] == "MultiPolygon" else [geo["coordinates"]]
        return [poly[0] for poly in polys]

    hedef = None
    dolgu = tuple(min(255, v + 26) for v in zemin)
    for ft in iller:
        secili = ft["properties"]["name"].lower() == il.lower()
        for halka in halkalar(ft["geometry"]):
            c.polygon([p(*pt) for pt in halka], fill=vurgu if secili else dolgu, outline=(70, 76, 88))
        if secili:
            hedef = ft
    # ilin ortasına iğne
    noktalar = [p(*pt) for h in halkalar(hedef["geometry"]) for pt in h]
    cx = sum(x for x, _ in noktalar) / len(noktalar)
    cy = sum(y for _, y in noktalar) / len(noktalar)
    c.ellipse([cx - 16, cy - 16, cx + 16, cy + 16], fill=BEYAZ, outline=vurgu, width=6)
    f = font(KALIN, 38)
    yazi = buyuk(il)
    w = c.textlength(yazi, font=f)
    lx = min(max(cx - w / 2, x0), x1 - w)
    ly = cy - 90 if cy - 90 >= y0 else cy + 34  # kuzey kıyısındaki illerde etiket iğnenin altına
    c.rounded_rectangle([lx - 16, ly, lx + w + 16, ly + 56], radius=8, fill=BEYAZ)
    c.text((lx, ly + 6), yazi, font=f, fill=zemin)


# ---------- kart türleri ----------

def ciz_kart(haber, marka, kullanici_adi, cikti, sayfa=None, kaydir=False):
    konu = KONULAR.get(haber.get("konu", "gundem"), KONULAR["gundem"])
    _, vurgu, zemin, _ = konu
    img = Image.new("RGB", (G, Y), zemin)
    c = ImageDraw.Draw(img)

    if haber.get("foto"):
        foto = haber["foto"]
        resim = ImageOps.fit(Image.open(foto["yol"]).convert("RGB"), (G, 660), centering=(.5, .6))
        img.paste(resim, (0, 0))
        # fotoğrafın altını zemine erit
        perde = Image.new("RGB", (G, 220), zemin)
        maske = Image.linear_gradient("L").resize((G, 220))
        img.paste(perde, (0, 440), maske)
        ust = Image.new("RGB", (G, 200), (0, 0, 0))
        img.paste(ust, (0, 0), Image.linear_gradient("L").rotate(180).resize((G, 200)).point(lambda v: v * .55))
        ust_serit(c, marka, konu, sayfa=sayfa)
        fk = font(NORMAL, 22)
        not_ = foto["not"]
        c.text((G - KENAR - c.textlength(not_, font=fk), 612), not_, font=fk, fill=(200, 205, 212))
        metin_blogu(c, haber, 680, 1160, vurgu, en_buyuk=80, ozet_satir=2)
    elif haber.get("il"):
        ust_serit(c, marka, konu, sayfa=sayfa)
        il_haritasi(c, haber["il"], (KENAR - 20, 170, G - KENAR + 20, 560), vurgu, zemin)
        metin_blogu(c, haber, 600, 1160, vurgu, en_buyuk=84, ozet_satir=3)
    elif haber.get("rakam"):
        ust_serit(c, marka, konu, sayfa=sayfa)
        fr = font(KALIN, 230)
        c.text((KENAR - 8, 190), haber["rakam"], font=fr, fill=vurgu)
        c.text((KENAR, 450), buyuk(haber.get("rakam_birim", "")), font=font(KALIN, 44), fill=GRI)
        metin_blogu(c, haber, 540, 1160, vurgu, en_buyuk=84, ozet_satir=4)
    else:
        ust_serit(c, marka, konu, sayfa=sayfa)
        metin_blogu(c, haber, 190, 1160, vurgu)

    alt_serit(c, haber, kullanici_adi, vurgu, kaydir)
    img.save(cikti, "JPEG", quality=92)
    return cikti


KONU_ETIKETI = {"gundem": "#gündem", "afet": "#hava #afet", "ekonomi": "#ekonomi", "dunya": "#dünya",
                "spor": "#spor", "asayis": "#asayiş"}


def aciklama(haber, hashtagler, karusel=False):
    parca = []
    if haber.get("kanca"):
        parca.append(haber["kanca"])
    parca.append(haber["baslik"])
    if haber.get("ozet"):
        parca.append(haber["ozet"])
    if karusel:
        parca.append("Detaylar slaytlarda, kaydır 👉")
    kaynak = "Kaynak: " + ", ".join([haber["kaynak"]] + haber.get("diger_kaynaklar", []))
    parca.append(f"{kaynak}\n{haber['link']}")
    if haber.get("foto"):
        parca.append(haber["foto"]["not"])
    parca.append("Gündemi kaçırmamak için takip et.")
    parca.append((hashtagler + " " + KONU_ETIKETI.get(haber.get("konu", "gundem"), "")).strip())
    return "\n\n".join(p for p in parca if p)
