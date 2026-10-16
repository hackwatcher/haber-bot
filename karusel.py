"""Tek bir haberden karusel: kapak kartı + bilgi slaytları + kaynak/takip slaytı.

Bilgi slaytları haber["slaytlar"] listesinden gelir; her biri {"etiket", "metin" | "maddeler", "rakam"?, "rakam_birim"?}.
Metinler haberin tam metninden kendi cümlelerimizle özetlenir (birebir kopya değil).
"""

import os

from PIL import Image, ImageDraw

import kart
from kart import BEYAZ, G, GRI, KALIN, KENAR, KONULAR, NORMAL, SOLUK, Y, buyuk, font, sar

GENIS = G - 2 * KENAR


def zemin(haber, marka, sayfa):
    konu = KONULAR.get(haber.get("konu", "gundem"), KONULAR["gundem"])
    img = Image.new("RGB", (G, Y), konu[2])
    c = ImageDraw.Draw(img)
    kart.ust_serit(c, marka, konu, sayfa=sayfa)
    return img, c, konu[1]


def _yerlesim(c, slayt, k):
    """Slayt içeriğini k ölçeğinde parçalara böler: [(tür, veri, font, yükseklik)]."""
    p = [("etiket", buyuk(slayt["etiket"]), font(KALIN, 46), 100)]
    if slayt.get("rakam"):
        boy = int(200 * k)
        while boy > 90 and c.textlength(slayt["rakam"], font=font(KALIN, boy)) > GENIS:
            boy -= 10
        p.append(("rakam", slayt["rakam"], font(KALIN, boy), int(boy * 1.1)))
    for r, aciklama in slayt.get("rakamlar", []):
        boy = int(110 * k)
        while boy > 60 and c.textlength(r, font=font(KALIN, boy)) > GENIS:
            boy -= 6
        fa = font(NORMAL, int(38 * k))
        sat = sar(c, aciklama, fa, GENIS)
        p.append(("rakamsatiri", (r, sat), (font(KALIN, boy), fa), int(boy * 1.08) + len(sat) * int(fa.size * 1.35) + 44))
    if slayt.get("metin"):
        tek = not (slayt.get("rakam") or slayt.get("maddeler"))  # "Ne oldu?": tek paragraf, büyük ve kalın
        f = font(KALIN, int(60 * k)) if tek else font(NORMAL, int(42 * k))
        sat = sar(c, slayt["metin"], f, GENIS)
        p.append(("metin", sat, f, len(sat) * int(f.size * 1.38)))
    for m in slayt.get("maddeler", []):
        f = font(NORMAL, int(44 * k))
        sat = sar(c, m, f, GENIS - 60)
        p.append(("madde", sat, f, len(sat) * int(f.size * 1.42) + 36))
    if slayt.get("alinti"):
        f = font(KALIN, int(56 * k))
        sat = sar(c, slayt["alinti"], f, GENIS)
        p.append(("tirnak", "“", font(KALIN, 200), 120))
        p.append(("metin", sat, f, len(sat) * int(f.size * 1.32) + 30))
        if slayt.get("kim"):
            fk = font(NORMAL, int(38 * k))
            ks = sar(c, "— " + slayt["kim"], fk, GENIS)
            p.append(("kim", ks, fk, len(ks) * int(fk.size * 1.4)))
    return p


def bilgi_slayti(haber, slayt, marka, sayfa, cikti, kaydir=True):
    img, c, vurgu = zemin(haber, marka, sayfa)
    alan = 1160 - 180
    for k in [x / 100 for x in range(125, 55, -5)]:  # az yazıda büyük başla, sığana kadar küçült
        parcalar = _yerlesim(c, slayt, k)
        toplam = sum(p[3] for p in parcalar)
        if toplam <= alan:
            break
    y = 180 + max(0, (alan - toplam) // 2)

    for tur, veri, f, h in parcalar:
        if tur == "etiket":
            c.rectangle([KENAR, y + 6, KENAR + 12, y + 50], fill=vurgu)
            c.text((KENAR + 32, y), veri, font=f, fill=vurgu)
        elif tur == "rakam":
            c.text((KENAR - 6, y - int(f.size * 0.12)), veri, font=f, fill=BEYAZ)
        elif tur == "rakamsatiri":
            (r, sat), (fr, fa) = veri, f
            c.text((KENAR - 4, y - int(fr.size * 0.1)), r, font=fr, fill=vurgu)
            yy = y + int(fr.size * 1.08)
            for s in sat:
                c.text((KENAR, yy), s, font=fa, fill=BEYAZ)
                yy += int(fa.size * 1.35)
        elif tur == "metin":
            satir = int(f.size * (1.32 if slayt.get("alinti") else 1.38))
            for i, s in enumerate(veri):
                c.text((KENAR, y + i * satir), s, font=f, fill=BEYAZ)
        elif tur == "madde":
            c.ellipse([KENAR + 4, y + int(f.size * .45), KENAR + 22, y + int(f.size * .45) + 18], fill=vurgu)
            for i, s in enumerate(veri):
                c.text((KENAR + 60, y + i * int(f.size * 1.42)), s, font=f, fill=BEYAZ)
        elif tur == "tirnak":
            c.text((KENAR - 10, y - 40), veri, font=f, fill=vurgu)
        elif tur == "kim":
            for i, s in enumerate(veri):
                c.text((KENAR, y + i * int(f.size * 1.4)), s, font=f, fill=GRI)
        y += h

    c.line([KENAR, 1190, G - KENAR, 1190], fill=(45, 50, 60), width=2)
    if kaydir:
        kart.kaydir_oku(c, vurgu)
    img.save(cikti, "JPEG", quality=92)
    return cikti


def kapanis(haber, marka, kullanici_adi, sayfa, cikti):
    konu = KONULAR.get(haber.get("konu", "gundem"), KONULAR["gundem"])
    img, c, vurgu = zemin(haber, marka, sayfa)
    y = 330
    c.text((KENAR, y), "KAYNAK", font=font(KALIN, 40), fill=vurgu)
    y += 70
    kaynaklar = [haber["kaynak"]] + haber.get("diger_kaynaklar", [])
    c.text((KENAR, y), ", ".join(kaynaklar), font=font(KALIN, 64), fill=BEYAZ)
    y += 100
    for s in sar(c, "Haberin tamamı için kaynağa bakabilirsin. Linki açıklamada.", font(NORMAL, 36), GENIS):
        c.text((KENAR, y), s, font=font(NORMAL, 36), fill=GRI)
        y += 52
    y += 120
    fb = font(KALIN, 92)
    for s in ["GÜNDEMİ", "KAÇIRMA."]:
        c.text((KENAR - 4, y), s, font=fb, fill=BEYAZ)
        y += 106
    y += 40
    fk = font(KALIN, 44)
    yazi = "TAKİP ET  " + kullanici_adi
    w = c.textlength(yazi, font=fk)
    c.rounded_rectangle([KENAR, y, KENAR + w + 70, y + 96], radius=14, fill=vurgu)
    c.text((KENAR + 35, y + 24), yazi, font=fk, fill=konu[3])
    c.text((KENAR, y + 140), "Kaydet, ihtiyacı olana gönder.", font=font(NORMAL, 32), fill=SOLUK)
    img.save(cikti, "JPEG", quality=92)
    return cikti


def karusel(haber, marka, kullanici_adi, klasor, video=False):
    """Slayt yollarını döndürür (Instagram en fazla 10 slayt alır).

    video=True: Reels için; "KAYDIR" oku ve sayfa numarası yok (video kendisi akıyor).
    """
    os.makedirs(klasor, exist_ok=True)
    slaytlar = haber.get("slaytlar", [])[:8]
    toplam = len(slaytlar) + 2
    no = (lambda i: None) if video else (lambda i: (i, toplam))
    on = "v" if video else ""
    yollar = [kart.ciz_kart(dict(haber, ozet=""), marka, kullanici_adi, os.path.join(klasor, f"{on}01.jpg"),
                            sayfa=no(1), kaydir=not video)]
    for i, s in enumerate(slaytlar, 2):
        yollar.append(bilgi_slayti(haber, s, marka, no(i), os.path.join(klasor, f"{on}{i:02d}.jpg"),
                                   kaydir=not video))
    yollar.append(kapanis(haber, marka, kullanici_adi, no(toplam), os.path.join(klasor, f"{on}{toplam:02d}.jpg")))
    return yollar
